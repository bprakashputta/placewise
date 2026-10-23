"""Hybrid retrieval over CURRENT resume sections (the current_chunks view).

    hard filters (validated profile fields: license+state, metro or relocation, discipline, years)
      → vector search (Voyage query embedding, pgvector HNSW, cosine)
      → keyword search (Postgres full-text, OR of the query terms, ts_rank_cd)
      → Reciprocal Rank Fusion (RRF, k=60) → group by candidate

Hard filters come from code-verified fields, never from the embedding, so "Texas PE" can't be
satisfied by a resume that merely mentions Texas and engineering.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
from langchain_voyageai import VoyageAIEmbeddings
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from ..db import pool

EMBED_MODEL = "voyage-4-large"
RRF_K = 60
_embedder: VoyageAIEmbeddings | None = None


class Filters(BaseModel):
    discipline: str | None = None
    metro: str | None = Field(None, description="DFW | Houston | Austin | San Antonio | Other; relocators also match")
    license_codes: list[str] = Field(default_factory=list, description="All required, e.g. ['PE:TX']")
    min_years: float | None = None
    quality: str | None = None


@dataclass
class Hit:
    chunk_id: int
    person_id: int
    resume_file_id: int
    section: str
    content: str
    vec_rank: int | None = None
    kw_rank: int | None = None
    rrf: float = 0.0
    rerank: float | None = None


@dataclass
class CandidateHit:
    person_id: int
    score: float
    chunks: list[Hit] = field(default_factory=list)


def _embedder_() -> VoyageAIEmbeddings:
    global _embedder
    if _embedder is None:
        _embedder = VoyageAIEmbeddings(model=EMBED_MODEL)
    return _embedder


def _where(f: Filters) -> tuple[str, list]:
    sql, args = ["TRUE"], []
    if f.discipline:
        sql.append("p.discipline = %s")
        args.append(f.discipline)
    if f.metro:
        sql.append("(p.metro = %s OR p.open_to_relocation)")
        args.append(f.metro)
    for code in f.license_codes:
        sql.append("%s = ANY(p.license_codes)")
        args.append(code)
    if f.min_years is not None:
        sql.append("p.years_experience >= %s")
        args.append(f.min_years)
    if f.quality:
        sql.append("rf.quality = %s")
        args.append(f.quality)
    return " AND ".join(sql), args


def _or_query(text: str) -> str:
    words = [w for w in re.findall(r"[A-Za-z0-9+#.-]{2,}", text) if w.lower() not in {"and", "or", "the", "with"}]
    return " OR ".join(words) if words else text


async def vector_search(query: str, f: Filters, k: int = 50) -> list[Hit]:
    vec = np.array(await _embedder_().aembed_query(query), dtype=np.float32)
    where, args = _where(f)
    async with pool().connection() as conn:
        async with conn.transaction():
            # Filtered HNSW: iterative scans keep fetching until enough rows pass the filters (pgvector 0.8)
            await conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
            await conn.execute("SET LOCAL hnsw.ef_search = 200")
            cur = conn.cursor(row_factory=dict_row)
            await cur.execute(
                f"""SELECT c.id, c.person_id, c.resume_file_id, c.section, c.content
                    FROM current_chunks c JOIN profiles p ON p.resume_file_id = c.resume_file_id
                    JOIN resume_files rf ON rf.id = c.resume_file_id
                    WHERE {where} ORDER BY c.embedding <=> %s LIMIT %s""", [*args, vec, k])
            rows = await cur.fetchall()
    return [Hit(r["id"], r["person_id"], r["resume_file_id"], r["section"], r["content"], vec_rank=i + 1)
            for i, r in enumerate(rows)]


async def keyword_search(query: str, f: Filters, k: int = 50) -> list[Hit]:
    where, args = _where(f)
    async with pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            f"""SELECT c.id, c.person_id, c.resume_file_id, c.section, c.content,
                       ts_rank_cd(c.tsv, q) AS rank
                FROM current_chunks c JOIN profiles p ON p.resume_file_id = c.resume_file_id
                JOIN resume_files rf ON rf.id = c.resume_file_id,
                     websearch_to_tsquery('english', %s) q
                WHERE c.tsv @@ q AND {where} ORDER BY rank DESC LIMIT %s""", [_or_query(query), *args, k])
        rows = await cur.fetchall()
    return [Hit(r["id"], r["person_id"], r["resume_file_id"], r["section"], r["content"], kw_rank=i + 1)
            for i, r in enumerate(rows)]


def fuse(vec: list[Hit], kw: list[Hit]) -> list[Hit]:
    """Reciprocal Rank Fusion: robust to the two scores being on different scales."""
    by_id: dict[int, Hit] = {}
    for h in vec + kw:
        cur = by_id.setdefault(h.chunk_id, h)
        if h.vec_rank:
            cur.vec_rank = h.vec_rank
        if h.kw_rank:
            cur.kw_rank = h.kw_rank
    for h in by_id.values():
        h.rrf = (1 / (RRF_K + h.vec_rank) if h.vec_rank else 0) + (1 / (RRF_K + h.kw_rank) if h.kw_rank else 0)
    return sorted(by_id.values(), key=lambda h: h.rrf, reverse=True)


def group_by_candidate(hits: list[Hit], score_attr: str = "rrf", per_person: int = 3) -> list[CandidateHit]:
    """Best chunk score per candidate, plus a small bonus for several matching sections."""
    groups: dict[int, CandidateHit] = {}
    for h in hits:
        s = getattr(h, score_attr) or 0.0
        g = groups.setdefault(h.person_id, CandidateHit(h.person_id, 0.0))
        if len(g.chunks) < per_person:
            g.chunks.append(h)
    for g in groups.values():
        scores = sorted((getattr(c, score_attr) or 0.0 for c in g.chunks), reverse=True)
        g.score = scores[0] + 0.15 * sum(scores[1:])
    return sorted(groups.values(), key=lambda g: g.score, reverse=True)


async def hybrid(query: str, f: Filters, k: int = 50, mode: str = "hybrid") -> list[Hit]:
    vec = await vector_search(query, f, k) if mode in ("hybrid", "vector") else []
    kw = await keyword_search(query, f, k) if mode in ("hybrid", "keyword") else []
    return fuse(vec, kw)
