"""Where ingest files come from.

- seed:   data/seed/resumes/<folder>/<file> (mounted read-only; the answer key is NOT mounted)
- upload: /app/storage/uploads/<sha256>/<filename> (shared volume between api and worker)
"""
from __future__ import annotations

import os
from pathlib import Path

SEED_RESUMES = Path(os.environ.get("PLACEWISE_DATA_DIR", "/app/data")) / "seed" / "resumes"
STORAGE = Path(os.environ.get("PLACEWISE_STORAGE_DIR", "/app/storage"))
UPLOADS = STORAGE / "uploads"
PREVIEW_NAME = "_preview.pdf"


def seed_original(folder: str) -> Path:
    base = (SEED_RESUMES / folder).resolve()
    if SEED_RESUMES.resolve() not in base.parents:
        raise ValueError("bad seed folder")
    files = [p for p in sorted(base.iterdir()) if p.name != PREVIEW_NAME]
    if not files:
        raise FileNotFoundError(f"no resume file in {folder}")
    return files[0]


def resolve_file(job: dict) -> Path:
    if job["source"] == "seed":
        return seed_original(job["source_ref"])
    path = (STORAGE / job["payload"]["storage_path"]).resolve()
    if STORAGE.resolve() not in path.parents:
        raise ValueError("bad storage path")
    return path
