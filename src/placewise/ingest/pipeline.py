"""Ingest pipeline entry point used by the worker: runs the LangGraph ingest graph for one job."""
from __future__ import annotations

from .graph import GRAPH


async def run_job(job: dict) -> tuple[str, dict, int | None]:
    final = await GRAPH.ainvoke(
        {"job": job},
        config={"run_name": f"ingest:{job['source_ref']}", "tags": ["ingest", job["source"]],
                "metadata": {"job_id": job["id"], "source": job["source"], "source_ref": job["source_ref"]}})
    outcome = final["outcome"]
    return outcome["status"], outcome, outcome.get("resume_file_id")
