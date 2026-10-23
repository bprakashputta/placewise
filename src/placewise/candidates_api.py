"""Candidate API for the portal: list/filter, detail, resume view/download, upload.
Every route requires a signed-in user (applied in main.py)."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from psycopg.rows import dict_row

from .db import pool
from .ingest import queue
from .ingest.parse import sniff
from .ingest.sources import PREVIEW_NAME, SEED_RESUMES, STORAGE, UPLOADS

router = APIRouter(prefix="/api/candidates", tags=["candidates"])
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MEDIA = {"pdf": "application/pdf", "txt": "text/plain; charset=utf-8",
         "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


@router.get("")
async def list_candidates(
    q: str | None = None, discipline: str | None = None, metro: str | None = None,
    license: str | None = Query(None, description="e.g. PE:TX or LEED_AP"), min_years: float | None = None,
    quality: str | None = None, limit: int = 50, offset: int = 0,
) -> dict:
    limit, offset = max(1, min(limit, 200)), max(0, offset)
    where, args = ["TRUE"], []
    for col, val in (("discipline", discipline), ("metro", metro), ("quality", quality)):
        if val:
            where.append(f"{col} = %s")
            args.append(val)
    if license:
        where.append("%s = ANY(license_codes)")
        args.append(license)
    if min_years is not None:
        where.append("years_experience >= %s")
        args.append(min_years)
    if q:
        where.append("(full_name ILIKE %s OR headline ILIKE %s OR city ILIKE %s OR %s = ANY(software))")
        esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")   # literal % and _
        like = f"%{esc}%"
        args += [like, like, like, q]
    sql_where = " AND ".join(where)
    async with pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(f"SELECT count(*) AS n FROM current_candidates WHERE {sql_where}", args)
        total = (await cur.fetchone())["n"]
        await cur.execute(
            f"""SELECT person_id, full_name, headline, discipline, subdiscipline, city, state, metro, years_experience,
                       license_codes, quality, quality_issues, processed_at
                FROM current_candidates WHERE {sql_where}
                ORDER BY processed_at DESC NULLS LAST, person_id DESC LIMIT %s OFFSET %s""", [*args, limit, offset])
        rows = await cur.fetchall()
    return {"total": total, "items": rows, "limit": limit, "offset": offset}


@router.get("/facets")
async def facets() -> dict:
    """Counts for filter dropdowns."""
    async with pool().connection() as conn:
        out = {}
        for col in ("discipline", "metro", "quality"):
            cur = await conn.execute(f"SELECT {col}, count(*) FROM current_candidates WHERE {col} IS NOT NULL "
                                     f"GROUP BY 1 ORDER BY 2 DESC")
            out[col] = {k: n for k, n in await cur.fetchall()}
        cur = await conn.execute("SELECT code, count(*) FROM current_candidates, unnest(license_codes) code "
                                 "GROUP BY 1 ORDER BY 2 DESC")
        out["license"] = {k: n for k, n in await cur.fetchall()}
        cur = await conn.execute("SELECT status, count(*) FROM resume_files GROUP BY 1")
        out["files"] = {k: n for k, n in await cur.fetchall()}
    return out


@router.get("/needs-attention")
async def needs_attention() -> list[dict]:
    """Files that couldn't be processed (scans, corrupt files), with the reason."""
    async with pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute("""SELECT id AS resume_file_id, filename, quality_issues, error AS reason, created_at
                             FROM resume_files WHERE status = 'needs_attention' ORDER BY id DESC""")
        return await cur.fetchall()


@router.get("/{person_id}")
async def candidate(person_id: int) -> dict:
    async with pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            """SELECT p.id AS person_id, rf.id AS resume_file_id, rf.filename, rf.quality, rf.quality_issues,
                      rf.parse_info, rf.processed_at, pr.data AS profile, pr.years_experience, pr.metro,
                      pr.license_codes, pr.software, pr.sectors
               FROM people p JOIN resume_files rf ON rf.person_id = p.id AND rf.is_current
               JOIN profiles pr ON pr.resume_file_id = rf.id WHERE p.id = %s""", (person_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "candidate not found")
        await cur.execute("""SELECT id AS resume_file_id, filename, status, quality, is_current, created_at, processed_at
                             FROM resume_files WHERE person_id = %s ORDER BY id DESC""", (person_id,))
        row["versions"] = await cur.fetchall()
    findings = (row.get("parse_info") or {}).get("findings", [])
    notes = (row.get("parse_info") or {}).get("validation_notes", [])
    row["findings"], row["validation_notes"] = findings, notes
    row.pop("parse_info", None)
    row["profile"].pop("email", None)  # contact details only via an explicit, audited action (later)
    row["profile"].pop("phone", None)
    return row


async def _file_path(resume_file_id: int) -> tuple[Path, str, str]:
    async with pool().connection() as conn:
        cur = await conn.execute("SELECT source, storage_path, filename FROM resume_files WHERE id = %s",
                                 (resume_file_id,))
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "file not found")
    source, rel, filename = row
    root = SEED_RESUMES if source == "seed" else STORAGE
    path = (root / rel).resolve()
    if root.resolve() not in path.parents or not path.exists():
        raise HTTPException(404, "file not found")
    return path, filename, source


@router.get("/files/{resume_file_id}")
async def download_file(resume_file_id: int):
    path, filename, _ = await _file_path(resume_file_id)
    return FileResponse(path, filename=filename, content_disposition_type="attachment",
                        media_type=MEDIA.get(path.suffix.lstrip("."), "application/octet-stream"))


@router.get("/files/{resume_file_id}/view")
async def view_file(resume_file_id: int):
    """Inline PDF for the in-browser viewer: the original PDF, or a rendered preview if one exists."""
    path, filename, _ = await _file_path(resume_file_id)
    target = path if path.suffix == ".pdf" else path.parent / PREVIEW_NAME
    if not target.exists():
        raise HTTPException(404, f"No in-browser preview for this {path.suffix.lstrip('.').upper()} file. "
                                 "Use Download to open the original.")
    return FileResponse(target, media_type="application/pdf", content_disposition_type="inline",
                        filename=Path(filename).with_suffix(".pdf").name)


@router.post("/upload")
async def upload(file: UploadFile) -> dict:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(415, "The file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 10 MB")
    kind = sniff(data)
    if kind not in ("pdf", "docx", "txt"):
        raise HTTPException(415, "Only PDF, DOCX or TXT resumes are supported")
    sha = hashlib.sha256(data).hexdigest()
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", Path(file.filename or "").name).lstrip(". ")
    stem, dot, ext = name.rpartition(".")
    safe = f"{stem[:110]}.{ext[:10]}" if dot and stem else name[:120]  # keep the extension when trimming
    if not safe or "." not in safe:
        safe = f"resume.{kind}"  # also covers names like "." / ".." that would point at a directory
    folder = UPLOADS / sha
    folder.mkdir(parents=True, exist_ok=True)
    (folder / safe).write_bytes(data)
    async with pool().connection() as conn:
        job_id = await queue.enqueue(conn, "upload", sha, {"storage_path": f"uploads/{sha}/{safe}"})
    return {"queued": job_id is not None, "job_id": job_id, "sha256": sha,
            "message": "Queued for processing" if job_id else "This exact file was already submitted"}
