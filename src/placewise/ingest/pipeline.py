"""Ingest pipeline entry point. Step A placeholder: confirms the worker can locate the file.
Steps B-D replace this with the LangGraph ingest graph (parse → screen → extract → validate →
blind → chunk → embed → store)."""
from __future__ import annotations

from .sources import resolve_file


async def run_job(job: dict) -> tuple[str, dict, int | None]:
    path = resolve_file(job)
    return "done", {"placeholder": True, "file": path.name, "bytes": path.stat().st_size}, None
