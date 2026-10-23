"""Ingest worker: claims jobs from the Postgres queue and runs the ingest pipeline.

Run as its own container:  python -m placewise.worker
Scale out with:            docker compose up -d --scale worker=3
Each process runs WORKER_CONCURRENCY jobs at a time and shuts down gracefully on SIGTERM
(finishes in-flight jobs; anything interrupted is reclaimed after STALE_AFTER_MIN).
"""
from __future__ import annotations

import asyncio
import os
import signal
import socket
import time
import traceback

from .db import close_pool, open_pool, pool
from .ingest import queue
from .migrate import migrate

CONCURRENCY = int(os.environ.get("WORKER_CONCURRENCY", "4"))
IDLE_SLEEP_S = 2.0
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"
_stop = asyncio.Event()


async def process(job: dict) -> tuple[str, dict, int | None]:
    """Run the ingest pipeline for one job. Returns (status, result, resume_file_id)."""
    from .ingest.pipeline import run_job  # imported lazily: heavy deps load once per process

    return await run_job(job)


async def slot(n: int) -> None:
    while not _stop.is_set():
        async with pool().connection() as conn:
            job = await queue.claim(conn, f"{WORKER_ID}#{n}")
        if job is None:
            try:
                await asyncio.wait_for(_stop.wait(), timeout=IDLE_SLEEP_S)
            except asyncio.TimeoutError:
                pass
            continue
        t0 = time.perf_counter()
        try:
            status, result, file_id = await process(job)
            async with pool().connection() as conn:
                await queue.finish(conn, job["id"], status, result, file_id)
            print(f"[{WORKER_ID}#{n}] job {job['id']} {job['source_ref']} → {status} "
                  f"({time.perf_counter() - t0:.1f}s)", flush=True)
        except Exception as e:  # unexpected error: retry with backoff, keep the traceback
            err = f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=5)}"
            async with pool().connection() as conn:
                new_status = await queue.fail(conn, job, err)
            print(f"[{WORKER_ID}#{n}] job {job['id']} error → {new_status}: {type(e).__name__}: {e}", flush=True)


async def reaper() -> None:
    while not _stop.is_set():
        async with pool().connection() as conn:
            n = await queue.reclaim_stale(conn)
        if n:
            print(f"[{WORKER_ID}] reclaimed {n} stale job(s)", flush=True)
        try:
            await asyncio.wait_for(_stop.wait(), timeout=60)
        except asyncio.TimeoutError:
            pass


async def main() -> None:
    await asyncio.to_thread(migrate)
    await open_pool()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _stop.set)
    print(f"[{WORKER_ID}] started with concurrency {CONCURRENCY}", flush=True)
    await asyncio.gather(reaper(), *(slot(i) for i in range(CONCURRENCY)))
    await close_pool()
    print(f"[{WORKER_ID}] stopped", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
