"""Dev-only API for the live Seed page. Registered under /api/dev/seed ONLY when APP_ENV=dev.

Reads data/seed/public (aggregates and dev-split showcase) and data/seed/resumes (the files).
It never reads data/seed/truth, which isn't even mounted into the api container.
"""
import json
import os
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

SEED_DIR = Path(os.environ.get("PLACEWISE_DATA_DIR", "/app/data")) / "seed"
PUBLIC, RESUMES = SEED_DIR / "public", SEED_DIR / "resumes"
SAMPLES = Path("/app/outputs/samples")
PREVIEW_NAME = "_preview.pdf"
MEDIA = {"pdf": "application/pdf", "txt": "text/plain; charset=utf-8",
         "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}

router = APIRouter(prefix="/api/dev/seed", tags=["dev: seed data"])


def _read(name: str, default):
    path = PUBLIC / name
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:  # file mid-replace; the next poll will succeed
        return default


@router.get("/status")
def status() -> dict:
    return {"progress": _read("progress.json", None), "stats": _read("stats.json", None),
            "showcase": _read("showcase.json", []), "job_orders": _read("job_orders.json", [])}


@router.get("/files")
def files() -> list:
    return _read("files.json", [])


def _folder(candidate_id: str) -> Path:
    if not (candidate_id.startswith("C") and candidate_id[1:].isdigit()):
        raise HTTPException(400, "bad candidate id")
    folder = (RESUMES / candidate_id).resolve()
    if RESUMES.resolve() not in folder.parents or not folder.is_dir():
        raise HTTPException(404, "not found")
    return folder


def _original(folder: Path) -> Path:
    found = next((f for f in sorted(folder.iterdir()) if f.name != PREVIEW_NAME), None)
    if found is None:
        raise HTTPException(404, "not found")
    return found


@router.get("/files/{candidate_id}")
def download(candidate_id: str):
    """The original file (PDF, DOCX or TXT), as a download."""
    found = _original(_folder(candidate_id))
    ext = found.suffix.lstrip(".")
    return FileResponse(found, media_type=MEDIA.get(ext, "application/octet-stream"), filename=found.name,
                        content_disposition_type="attachment")


@router.get("/files/{candidate_id}/view")
def view(candidate_id: str):
    """A PDF for in-browser viewing: the original if it is a PDF, otherwise its PDF preview."""
    folder = _folder(candidate_id)
    original = _original(folder)
    target = original if original.suffix == ".pdf" else folder / PREVIEW_NAME
    if not target.exists():
        # Check the file itself rather than assuming: a DOCX is a zip archive.
        if original.suffix == ".docx" and not zipfile.is_zipfile(original):
            raise HTTPException(409, "This DOCX can't be opened: the file appears to be corrupt. "
                                     "You can still download it to inspect.")
        raise HTTPException(404, f"No in-browser preview for this {original.suffix.lstrip('.').upper()} file yet. "
                                 "It's created on the next render. Use Download to open the original.")
    return FileResponse(target, media_type="application/pdf", content_disposition_type="inline",
                        filename=original.with_suffix(".pdf").name)


@router.get("/samples")
def samples() -> list[str]:
    return sorted(p.name for p in SAMPLES.glob("*.pdf")) if SAMPLES.exists() else []


@router.get("/samples/{name}")
def sample(name: str, download: bool = False):
    path = (SAMPLES / name).resolve()
    if path.parent != SAMPLES.resolve() or path.suffix != ".pdf" or not path.exists():
        raise HTTPException(404, "not found")
    return FileResponse(path, media_type="application/pdf", filename=name,
                        content_disposition_type="attachment" if download else "inline")
