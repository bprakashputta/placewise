"""The LangGraph ingest graph.

    receive ─┬─ duplicate ─────────────────────────────────────────────► END   (same bytes seen before)
             └─ parse_screen ─┬─ unusable ─► store_unusable ──────────► END   (scan / corrupt: needs attention)
                              └─ extract ─► validate ─► embed_store ──► END   (profile + searchable sections)

Duplicates and unreadable files are routed away BEFORE any paid model call. Every run is traced
in LangSmith as one trace with a span per node. File bytes never enter the graph state (traces stay
small); only the path and hash do.
"""
from __future__ import annotations

import hashlib
from typing import Any, TypedDict

from langchain_voyageai import VoyageAIEmbeddings
from langgraph.graph import END, START, StateGraph

from .chunk import blind_text, build_chunks
from .extract import PROMPT_VERSION, extract
from .parse import parse, sniff
from .screen import screen
from .sources import STORAGE, SEED_RESUMES, resolve_file
from .spend import check as spend_check
from .spend import log_call
from .store import (DuplicateFile, find_by_sha, get_cached_extraction, put_cached_extraction, store_processed,
                    store_unusable)
from .validate import validate

EMBED_MODEL = "voyage-4-large"
_embedder: VoyageAIEmbeddings | None = None


class IngestState(TypedDict, total=False):
    job: dict
    meta: dict
    duplicate_of: int
    parse_info: dict
    screen: dict
    clean_text: str
    extraction: dict
    validated: Any
    outcome: dict


def _embed() -> VoyageAIEmbeddings:
    global _embedder
    if _embedder is None:
        _embedder = VoyageAIEmbeddings(model=EMBED_MODEL, batch_size=64)
    return _embedder


async def receive(state: IngestState) -> IngestState:
    job = state["job"]
    path = resolve_file(job)
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    root = SEED_RESUMES if job["source"] == "seed" else STORAGE
    meta = {"sha256": sha, "filename": path.name, "size": len(data), "media_type": sniff(data),
            "source": job["source"], "source_ref": job["source_ref"], "storage_path": str(path.relative_to(root))}
    out: IngestState = {"meta": meta}
    existing = await find_by_sha(sha)
    if existing:
        out["duplicate_of"] = existing
    return out


async def parse_screen(state: IngestState) -> IngestState:
    job = state["job"]
    p = parse(resolve_file(job).read_bytes())
    s = screen(p)
    info = {"status": p.status, "file_type": p.file_type, "pages": p.pages, "columns_detected": p.columns_detected,
            "reason": p.reason, "hidden_chars": len(p.hidden_text), "findings": s.findings}
    return {"parse_info": info, "screen": {"quality": s.quality, "issues": s.issues, "findings": s.findings},
            "clean_text": s.clean_text}


async def do_extract(state: IngestState) -> IngestState:
    from ..promptlib import load

    ref, sha = state["job"]["source_ref"], state["meta"]["sha256"]
    model = load("ingest_extract_profile", PROMPT_VERSION)["model"]
    cached = await get_cached_extraction(sha, model, PROMPT_VERSION)
    if cached is not None:  # a retry: reuse the extraction we already paid for
        return {"extraction": {"profile": cached, "model": model, "cost_usd": 0.0, "cached": True}}
    await spend_check()
    ex = await extract(state["clean_text"], model_id=model, run_name="extract_profile", tags=["ingest"])
    await log_call(ref, "ingest.extract", ex.model, PROMPT_VERSION, ex.input_tokens, ex.output_tokens, ex.latency_ms,
                   ex.cost_usd, "ok" if ex.profile else "invalid_output", "; ".join(ex.problems) or None)
    if ex.profile is None:
        raise RuntimeError(f"extraction failed: {ex.problems}")  # the worker retries with backoff
    await put_cached_extraction(sha, ex.model, PROMPT_VERSION, ex.profile.model_dump(), ex.cost_usd)
    return {"extraction": {"profile": ex.profile.model_dump(), "model": ex.model, "cost_usd": round(ex.cost_usd, 5)}}


async def do_validate(state: IngestState) -> IngestState:
    from .schema import ExtractedProfile
    from .screen import Screen

    scr = Screen(**state["screen"], clean_text=state["clean_text"])
    v = validate(ExtractedProfile.model_validate(state["extraction"]["profile"]), state["clean_text"], scr)
    return {"validated": v}


async def embed_store(state: IngestState) -> IngestState:
    v = state["validated"]
    chunks = build_chunks(v.profile)
    vectors = await _embed().aembed_documents([c["content"] for c in chunks])
    try:
        file_id, person_id, new_person = await store_processed(
            state["meta"], state["parse_info"], v, chunks, vectors, blind_text(v.profile),
            state["extraction"]["model"], PROMPT_VERSION)
    except DuplicateFile as d:
        return {"outcome": {"status": "duplicate", "resume_file_id": d.file_id,
                            "reason": "identical file stored by a concurrent job"}}
    return {"outcome": {"status": "done", "resume_file_id": file_id, "person_id": person_id,
                        "new_person": new_person, "quality": v.quality, "issues": v.quality_issues,
                        "license_codes": v.license_codes, "chunks": len(chunks),
                        "cost_usd": state["extraction"]["cost_usd"]}}


async def store_unreadable(state: IngestState) -> IngestState:
    info = state["parse_info"]
    file_id = await store_unusable(state["meta"], info, state["screen"]["issues"], info.get("reason") or "unreadable")
    return {"outcome": {"status": "needs_attention", "resume_file_id": file_id, "reason": info.get("reason"),
                        "issues": state["screen"]["issues"]}}


async def finish_duplicate(state: IngestState) -> IngestState:
    return {"outcome": {"status": "duplicate", "resume_file_id": state["duplicate_of"],
                        "reason": "identical file already ingested"}}


def build_graph():
    g = StateGraph(IngestState)
    g.add_node("receive", receive)
    g.add_node("parse_screen", parse_screen)
    g.add_node("extract", do_extract)
    g.add_node("validate", do_validate)
    g.add_node("embed_store", embed_store)
    g.add_node("store_unusable", store_unreadable)
    g.add_node("duplicate", finish_duplicate)
    g.add_edge(START, "receive")
    g.add_conditional_edges("receive", lambda s: "duplicate" if s.get("duplicate_of") else "parse_screen",
                            ["duplicate", "parse_screen"])
    g.add_conditional_edges("parse_screen",
                            lambda s: "store_unusable" if s["screen"]["quality"] == "unusable" else "extract",
                            ["store_unusable", "extract"])
    g.add_edge("extract", "validate")
    g.add_edge("validate", "embed_store")
    for end in ("embed_store", "store_unusable", "duplicate"):
        g.add_edge(end, END)
    return g.compile()


GRAPH = build_graph()
