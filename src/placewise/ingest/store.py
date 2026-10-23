"""Persist ingest results. Each resume is saved in ONE transaction: person, file version, profile and
chunks all land together or not at all (no half-saved candidates)."""
from __future__ import annotations

import json
import re

import numpy as np
from psycopg import errors

from ..db import pool


def norm_email(e: str | None) -> str | None:
    return e.strip().lower() if e and "@" in e else None


def norm_phone(p: str | None) -> str | None:
    digits = re.sub(r"\D", "", p or "")
    return digits[-10:] if len(digits) >= 10 else None


async def find_by_sha(sha: str) -> int | None:
    async with pool().connection() as conn:
        cur = await conn.execute("SELECT id FROM resume_files WHERE sha256 = %s", (sha,))
        row = await cur.fetchone()
    return row[0] if row else None


async def store_unusable(meta: dict, parse_info: dict, issues: list[str], reason: str) -> int:
    async with pool().connection() as conn:
        try:
            cur = await conn.execute(
                """INSERT INTO resume_files (sha256, filename, media_type, size_bytes, source, source_ref, storage_path,
                       status, quality, quality_issues, parse_info, error, processed_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,'needs_attention','unusable',%s,%s,%s, now()) RETURNING id""",
                (meta["sha256"], meta["filename"], meta["media_type"], meta["size"], meta["source"], meta["source_ref"],
                 meta["storage_path"], issues, json.dumps(parse_info), reason))
        except errors.UniqueViolation:  # same bytes arrived concurrently: the other job owns it
            await conn.rollback()
            return await find_by_sha(meta["sha256"])
        return (await cur.fetchone())[0]


class DuplicateFile(Exception):
    """The same bytes were stored by a concurrent job while this one was processing."""

    def __init__(self, file_id: int):
        self.file_id = file_id


async def get_cached_extraction(sha: str, model: str, prompt_version: int) -> dict | None:
    async with pool().connection() as conn:
        cur = await conn.execute("SELECT profile FROM extraction_cache WHERE sha256=%s AND model=%s AND prompt_version=%s",
                                 (sha, model, prompt_version))
        row = await cur.fetchone()
    return row[0] if row else None


async def put_cached_extraction(sha: str, model: str, prompt_version: int, profile: dict, cost: float) -> None:
    async with pool().connection() as conn:
        await conn.execute(
            """INSERT INTO extraction_cache (sha256, model, prompt_version, profile, cost_usd) VALUES (%s,%s,%s,%s,%s)
               ON CONFLICT DO NOTHING""", (sha, model, prompt_version, json.dumps(profile), round(cost, 6)))


async def store_processed(meta: dict, parse_info: dict, v, chunks: list[dict], vectors: list[list[float]],
                          blind: str, model: str, prompt_version: int) -> tuple[int, int, bool]:
    """Returns (resume_file_id, person_id, new_person). Raises DuplicateFile on a concurrent identical file."""
    try:
        return await _store_processed(meta, parse_info, v, chunks, vectors, blind, model, prompt_version)
    except errors.UniqueViolation as e:
        if "resume_files_sha256_key" in str(e):
            raise DuplicateFile(await find_by_sha(meta["sha256"])) from e
        raise


async def _store_processed(meta: dict, parse_info: dict, v, chunks: list[dict], vectors: list[list[float]],
                           blind: str, model: str, prompt_version: int) -> tuple[int, int, bool]:
    prof = v.profile
    email, phone = norm_email(prof.get("email")), norm_phone(prof.get("phone"))
    async with pool().connection() as conn:
        async with conn.transaction():
            # Same person = same email, or same phone AND same name. A phone alone never merges
            # people (shared office lines; the eval caught over-merging with phone-only matching).
            cur = await conn.execute(
                """SELECT id FROM people
                   WHERE (%s::text IS NOT NULL AND email_norm = %s)
                      OR (%s::text IS NULL AND %s::text IS NOT NULL AND phone_norm = %s
                          AND lower(display_name) = lower(%s))
                   ORDER BY id LIMIT 1""",
                (email, email, email, phone, phone, prof.get("full_name") or ""))
            row = await cur.fetchone()
            new_person = row is None
            if new_person and email:
                # Race-safe: two versions of one person processed at the same moment both land here.
                cur = await conn.execute(
                    """INSERT INTO people (display_name, email_norm, phone_norm) VALUES (%s,%s,%s)
                       ON CONFLICT (email_norm) WHERE email_norm IS NOT NULL
                       DO UPDATE SET updated_at = now() RETURNING id, (xmax = 0) AS inserted""",
                    (prof.get("full_name"), email, phone))
                person_id, new_person = await cur.fetchone()
            elif new_person:
                cur = await conn.execute(
                    "INSERT INTO people (display_name, email_norm, phone_norm) VALUES (%s,%s,%s) RETURNING id",
                    (prof.get("full_name"), email, phone))
                person_id = (await cur.fetchone())[0]
            else:
                person_id = row[0]
                await conn.execute("UPDATE people SET display_name = %s, updated_at = now() WHERE id = %s",
                                   (prof.get("full_name"), person_id))
            await conn.execute("UPDATE resume_files SET is_current = FALSE WHERE person_id = %s AND is_current",
                               (person_id,))
            cur = await conn.execute(
                """INSERT INTO resume_files (person_id, sha256, filename, media_type, size_bytes, source, source_ref,
                       storage_path, status, quality, quality_issues, parse_info, is_current, processed_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'processed',%s,%s,%s,TRUE, now()) RETURNING id""",
                (person_id, meta["sha256"], meta["filename"], meta["media_type"], meta["size"], meta["source"],
                 meta["source_ref"], meta["storage_path"], v.quality, v.quality_issues,
                 json.dumps({**parse_info, "validation_notes": v.notes})))
            file_id = (await cur.fetchone())[0]
            await conn.execute(
                """INSERT INTO profiles (resume_file_id, person_id, data, full_name, headline, discipline, subdiscipline,
                       city, state, metro, open_to_relocation, years_experience, license_codes, software, sectors,
                       blind_text, model, prompt_version)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (file_id, person_id, json.dumps(prof), prof.get("full_name"), prof.get("headline"),
                 prof.get("discipline"), prof.get("subdiscipline"), prof.get("city"), prof.get("state"), v.metro,
                 prof.get("open_to_relocation"), v.years_experience, v.license_codes, v.software, v.sectors, blind,
                 model, prompt_version))
            async with conn.cursor() as cur2:
                await cur2.executemany(
                    """INSERT INTO chunks (resume_file_id, person_id, section, ordinal, content, embedding)
                       VALUES (%s,%s,%s,%s,%s,%s)""",
                    [(file_id, person_id, c["section"], c["ordinal"], c["content"], np.array(vec, dtype=np.float32))
                     for c, vec in zip(chunks, vectors)])
    return file_id, person_id, new_person
