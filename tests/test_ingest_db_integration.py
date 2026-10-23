"""Block 2 integration tests: migrations, the Postgres queue and the store transaction.

SKIPPED unless PLACEWISE_TEST_DATABASE_URL points at a THROWAWAY database (its name must end in
'_qa' or '_test'; the schema is dropped and recreated). Example (from the repo root):

    docker compose exec -T db psql -U placewise -d placewise -c "CREATE DATABASE placewise_qa"
    docker run --rm --network placewise_default -v "$PWD/tests:/app/tests:ro" -v "$PWD/prompts:/app/prompts:ro" \
      -e PLACEWISE_TEST_DATABASE_URL="postgresql://placewise:$(grep ^POSTGRES_PASSWORD= .env | cut -d= -f2-)@db:5432/placewise_qa" \
      placewise-api:ci pytest -q -p no:cacheprovider /app/tests/test_ingest_db_integration.py
    docker compose exec -T db psql -U placewise -d placewise -c "DROP DATABASE placewise_qa"
"""
import asyncio
import hashlib
import os
from types import SimpleNamespace
from urllib.parse import urlparse

import psycopg
import pytest

URL = os.environ.get("PLACEWISE_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="set PLACEWISE_TEST_DATABASE_URL to a throwaway database")

if URL:
    _dbname = urlparse(URL).path.lstrip("/")
    assert _dbname.endswith(("_qa", "_test")), f"refusing to run destructive tests against {_dbname!r}"


from placewise import db  # noqa: E402
from placewise.ingest import queue, store  # noqa: E402
from placewise.migrate import MIGRATIONS, migrate  # noqa: E402

ALL = sorted(p.stem for p in MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql"))


def _reset_schema():
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")


@pytest.fixture(scope="module", autouse=True)
def schema():
    _reset_schema()
    migrate(URL)
    yield


@pytest.fixture(autouse=True)
def clean():
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute("TRUNCATE chunks, profiles, ingest_jobs, resume_files, people, extraction_cache, llm_calls "
                     "RESTART IDENTITY CASCADE")
    yield


def arun(fn):
    """Run fn() with placewise.db's global pool pointed at the test database."""
    from psycopg_pool import AsyncConnectionPool

    async def main():
        p = AsyncConnectionPool(URL, min_size=1, max_size=12, open=False, configure=db._configure)
        await p.open(wait=True)
        db._pool = p
        try:
            return await fn(p)
        finally:
            db._pool = None
            await p.close()

    return asyncio.run(main())


def sql(q, args=()):
    with psycopg.connect(URL, autocommit=True) as conn:
        return conn.execute(q, args).fetchall()


# ---------- migrations ----------
def test_migrations_idempotent_from_scratch():
    _reset_schema()
    first = migrate(URL)
    assert first == ALL and first[:2] == ["001_core", "002_extraction_cache"]
    assert migrate(URL) == []
    tables = {r[0] for r in sql("SELECT tablename FROM pg_tables WHERE schemaname='public'")}
    assert {"people", "resume_files", "profiles", "chunks", "ingest_jobs", "llm_calls", "extraction_cache",
            "schema_migrations"} <= tables


def test_concurrent_migrate_runs_serialize():
    _reset_schema()

    async def both(_):
        return await asyncio.gather(asyncio.to_thread(migrate, URL), asyncio.to_thread(migrate, URL))

    async def run():
        return await both(None)

    a, b = asyncio.run(run())
    assert sorted([a, b], key=len) == [[], ALL]


# ---------- queue ----------
def test_enqueue_idempotent():
    async def go(p):
        async with p.connection() as c:
            first = await queue.enqueue(c, "seed", "C0001", {"folder": "C0001"})
            second = await queue.enqueue(c, "seed", "C0001", {"folder": "C0001"})
            other_source = await queue.enqueue(c, "upload", "C0001", {})
        return first, second, other_source

    first, second, other = arun(go)
    assert first and second is None and other and other != first
    assert sql("SELECT count(*) FROM ingest_jobs")[0][0] == 2


def test_concurrent_claims_never_return_the_same_job():
    n_jobs, n_workers = 30, 10

    async def go(p):
        async with p.connection() as c:
            for i in range(n_jobs):
                await queue.enqueue(c, "seed", f"C{i:04d}", {})

        async def worker(w):
            got = []
            while True:
                async with p.connection() as c:
                    job = await queue.claim(c, f"w{w}")
                if job is None:
                    return got
                got.append(job["id"])
                await asyncio.sleep(0)

        return await asyncio.gather(*(worker(w) for w in range(n_workers)))

    results = arun(go)
    ids = [i for r in results for i in r]
    assert len(ids) == n_jobs and len(set(ids)) == n_jobs
    rows = sql("SELECT status, attempts, locked_by IS NOT NULL FROM ingest_jobs")
    assert all(r == ("running", 1, True) for r in rows)


def test_claim_respects_not_before_and_status():
    async def go(p):
        async with p.connection() as c:
            jid = await queue.enqueue(c, "seed", "C1", {})
            await c.execute("UPDATE ingest_jobs SET not_before = now() + interval '1 hour' WHERE id = %s", (jid,))
            assert await queue.claim(c, "w") is None
            await c.execute("UPDATE ingest_jobs SET not_before = now(), status = 'done' WHERE id = %s", (jid,))
            return await queue.claim(c, "w")

    assert arun(go) is None


def test_fail_backs_off_then_fails_after_max_attempts():
    async def go(p):
        async with p.connection() as c:
            await queue.enqueue(c, "seed", "C1", {})
            statuses, delays = [], []
            for _ in range(3):
                await c.execute("UPDATE ingest_jobs SET not_before = now()")
                job = await queue.claim(c, "w")
                assert job is not None
                statuses.append(await queue.fail(c, job, "boom " + "x" * 5000, worker="w"))
                cur = await c.execute("SELECT extract(epoch FROM not_before - now()), length(error), status, "
                                      "locked_by FROM ingest_jobs")
                delays.append(await cur.fetchone())
            return statuses, delays

    statuses, rows = arun(go)
    assert statuses == ["queued", "queued", "failed"]
    assert 15 < rows[0][0] <= 20 and 35 < rows[1][0] <= 40           # 20s then 40s backoff
    assert all(r[1] == 2000 for r in rows)                           # error truncated
    assert rows[2][2] == "failed" and rows[2][3] is None
    assert sql("SELECT attempts FROM ingest_jobs")[0][0] == 3


def test_defer_does_not_consume_an_attempt():
    async def go(p):
        async with p.connection() as c:
            await queue.enqueue(c, "seed", "C1", {})
            job = await queue.claim(c, "w")
            await queue.defer(c, job, 30, "daily LLM spend cap reached")
            cur = await c.execute("SELECT status, attempts, error, locked_by, "
                                  "extract(epoch FROM not_before - now()) FROM ingest_jobs")
            return await cur.fetchone()

    status, attempts, error, locked_by, wait = arun(go)
    assert status == "queued" and attempts == 0 and "spend cap" in error and locked_by is None
    assert 29 * 60 < wait <= 30 * 60


def test_reclaim_stale_only_old_running_jobs():
    async def go(p):
        async with p.connection() as c:
            for ref in ("old", "fresh", "done"):
                await queue.enqueue(c, "seed", ref, {})
            await c.execute("UPDATE ingest_jobs SET status='running', locked_by='dead', "
                            "locked_at = now() - interval '11 minutes' WHERE source_ref='old'")
            await c.execute("UPDATE ingest_jobs SET status='running', locked_by='alive', "
                            "locked_at = now() - interval '5 minutes' WHERE source_ref='fresh'")
            await c.execute("UPDATE ingest_jobs SET status='done', "
                            "locked_at = now() - interval '1 hour' WHERE source_ref='done'")
            n = await queue.reclaim_stale(c)
            s = await queue.summary(c)
        return n, s

    n, s = arun(go)
    assert n == 1 and s == {"queued": 1, "running": 1, "done": 1}
    assert sql("SELECT status, locked_by FROM ingest_jobs WHERE source_ref='old'") == [("queued", None)]


def test_finish_keeps_result_and_file_id():
    async def go(p):
        async with p.connection() as c:
            jid = await queue.enqueue(c, "seed", "C1", {})
            job = await queue.claim(c, "w")
            await queue.finish(c, job["id"], "done", {"status": "done", "chunks": 3})
            return jid

    jid = arun(go)
    assert sql("SELECT status, result->>'chunks', locked_by FROM ingest_jobs WHERE id=%s", (jid,)) == \
        [("done", "3", None)]


# ---------- store ----------
def V(name="Jordan Sample", email="jordan@example.com", phone="(214) 555-0100"):
    prof = {"full_name": name, "email": email, "phone": phone, "headline": "Civil Engineer", "discipline": "civil",
            "city": "Dallas", "state": "TX", "jobs": [], "credentials": []}
    return SimpleNamespace(profile=prof, quality="polished", quality_issues=[], notes=[], metro="DFW",
                           years_experience=5.0, license_codes=["PE:TX"], software=["Civil 3D"], sectors=[])


def META(tag: str):
    sha = hashlib.sha256(tag.encode()).hexdigest()
    return {"sha256": sha, "filename": f"{tag}.txt", "size": 10, "media_type": "txt", "source": "upload",
            "source_ref": sha, "storage_path": f"uploads/{sha}/{tag}.txt"}


CHUNKS = [{"section": "summary", "ordinal": 0, "content": "[Civil Engineer | civil] summary: roads"}]
VECS = [[0.1] * 1024]


def save(tag, v):
    return store.store_processed(META(tag), {"findings": []}, v, CHUNKS, VECS, "blind", "m", 1)


def test_store_processed_writes_everything_in_one_go():
    fid, pid, new = arun(lambda p: save("a", V()))
    assert new is True
    assert sql("SELECT status, is_current, person_id FROM resume_files WHERE id=%s", (fid,)) == \
        [("processed", True, pid)]
    assert sql("SELECT email_norm, phone_norm FROM people WHERE id=%s", (pid,)) == \
        [("jordan@example.com", "2145550100")]
    assert sql("SELECT count(*), count(embedding) FROM chunks WHERE resume_file_id=%s", (fid,)) == [(1, 1)]
    assert sql("SELECT person_id, metro, license_codes FROM current_candidates") == [(pid, "DFW", ["PE:TX"])]


def test_same_email_is_same_person_and_new_version_becomes_current():
    async def go(p):
        a = await save("v1", V(email="Jordan@Example.com "))
        b = await save("v2", V(name="Jordan Q. Sample", email="jordan@example.com", phone=None))
        return a, b

    (f1, p1, n1), (f2, p2, n2) = arun(go)
    assert p1 == p2 and n1 is True and n2 is False
    assert sql("SELECT id, is_current FROM resume_files ORDER BY id") == [(f1, False), (f2, True)]
    assert sql("SELECT display_name FROM people") == [("Jordan Q. Sample",)]
    assert sql("SELECT count(*) FROM current_candidates") == [(1,)]


def test_same_phone_different_name_is_a_different_person():
    async def go(p):
        a = await save("a", V(name="Alex One", email=None, phone="214-555-0199"))
        b = await save("b", V(name="Blake Two", email=None, phone="(214) 555 0199"))
        c = await save("c", V(name="alex one", email=None, phone="+1 214.555.0199"))
        return a, b, c

    (_, pa, _), (_, pb, _), (_, pc, nc) = arun(go)
    assert pa != pb
    assert pc == pa and nc is False  # same phone AND same name (case-insensitive) → same person


def test_same_phone_but_different_email_is_different_person():
    async def go(p):
        a = await save("a", V(name="Alex", email="a@x.com", phone="2145550111"))
        b = await save("b", V(name="Alex", email="b@x.com", phone="2145550111"))
        return a, b

    (_, pa, _), (_, pb, _) = arun(go)
    assert pa != pb


def test_concurrent_new_person_same_email_upserts_one_person():
    async def go(p):
        return await asyncio.gather(save("x1", V()), save("x2", V()), save("x3", V()))

    res = arun(go)
    assert len({pid for _, pid, _ in res}) == 1
    assert sum(1 for _, _, new in res if new) == 1
    assert sql("SELECT count(*) FROM people") == [(1,)]
    assert sql("SELECT count(*) FROM resume_files WHERE is_current") == [(1,)]


def test_concurrent_identical_sha_raises_duplicate_file():
    async def go(p):
        return await asyncio.gather(save("same", V(email="one@x.com")), save("same", V(email="two@x.com")),
                                    return_exceptions=True)

    a, b = arun(go)
    ok = [r for r in (a, b) if isinstance(r, tuple)]
    dup = [r for r in (a, b) if isinstance(r, store.DuplicateFile)]
    assert len(ok) == 1 and len(dup) == 1, (a, b)
    assert dup[0].file_id == ok[0][0]
    # the loser's transaction rolled back completely: no orphan person, profile or chunk
    assert sql("SELECT count(*) FROM resume_files") == [(1,)]
    assert sql("SELECT count(*) FROM people") == [(1,)]
    assert sql("SELECT count(*) FROM chunks") == [(1,)]


def test_failed_store_leaves_nothing_half_saved():
    bad_vectors = [[0.1] * 3]  # wrong dimension → chunks insert fails at the end of the transaction

    async def go(p):
        with pytest.raises(Exception):
            await store.store_processed(META("bad"), {}, V(), CHUNKS, bad_vectors, "b", "m", 1)

    arun(go)
    for t in ("people", "resume_files", "profiles", "chunks"):
        assert sql(f"SELECT count(*) FROM {t}") == [(0,)], t


def test_store_unusable_and_concurrent_duplicate_returns_existing_id():
    async def go(p):
        a = await store.store_unusable(META("scan"), {"reason": "OCR"}, ["image_only_pdf"], "needs OCR")
        b = await store.store_unusable(META("scan"), {"reason": "OCR"}, ["image_only_pdf"], "needs OCR")
        return a, b, await store.find_by_sha(META("scan")["sha256"])

    a, b, found = arun(go)
    assert a == b == found
    assert sql("SELECT status, quality, quality_issues, error FROM resume_files") == \
        [("needs_attention", "unusable", ["image_only_pdf"], "needs OCR")]


def test_extraction_cache_roundtrip_and_no_overwrite():
    async def go(p):
        await store.put_cached_extraction("s", "m", 1, {"full_name": "A"}, 0.0123456)
        await store.put_cached_extraction("s", "m", 1, {"full_name": "B"}, 0.5)
        return (await store.get_cached_extraction("s", "m", 1), await store.get_cached_extraction("s", "m", 2))

    hit, miss = arun(go)
    assert hit == {"full_name": "A"} and miss is None


def test_concurrent_versions_of_existing_person_both_land():
    """Two new versions of an EXISTING person processed at the same moment."""
    async def go(p):
        await save("base", V())
        return await asyncio.gather(save("n1", V()), save("n2", V()), return_exceptions=True)

    res = arun(go)
    errors = [r for r in res if isinstance(r, BaseException)]
    assert not errors, f"concurrent versions of one person failed: {errors!r}"
    assert sql("SELECT count(*) FROM resume_files WHERE is_current") == [(1,)]


def test_current_chunks_view_hides_old_versions():
    async def go(p):
        await save("old", V())
        return await save("new", V())

    fid, _, _ = arun(go)
    assert sql("SELECT count(*) FROM chunks") == [(2,)]
    assert sql("SELECT resume_file_id FROM current_chunks") == [(fid,)]


# ---------- lock ownership (reviewer fixes) ----------
def test_only_the_lock_owner_can_finish_fail_or_defer():
    async def go(p):
        async with p.connection() as c:
            await queue.enqueue(c, "seed", "C1", {})
            job = await queue.claim(c, "owner")
            stranger_finish = await queue.finish(c, job["id"], "done", {"x": 1}, worker="stranger")
            stranger_fail = await queue.fail(c, job, "err", worker="stranger")
            await queue.defer(c, job, 30, "cap", worker="stranger")
            cur = await c.execute("SELECT status, locked_by, attempts FROM ingest_jobs")
            mid = await cur.fetchone()
            owner_finish = await queue.finish(c, job["id"], "done", {"x": 1}, worker="owner")
            return stranger_finish, stranger_fail, mid, owner_finish

    sf, sfail, mid, of = arun(go)
    assert sf is False and sfail == "lost" and mid == ("running", "owner", 1) and of is True
    assert sql("SELECT status, locked_by FROM ingest_jobs") == [("done", None)]


def test_late_finisher_after_reclaim_cannot_overwrite_new_owner():
    async def go(p):
        async with p.connection() as c:
            await queue.enqueue(c, "seed", "C1", {})
            old = await queue.claim(c, "old")
            await c.execute("UPDATE ingest_jobs SET locked_at = now() - interval '11 minutes'")
            assert await queue.reclaim_stale(c) == 1
            new = await queue.claim(c, "new")
            late = await queue.finish(c, old["id"], "failed", error="late", worker="old")
            late_fail = await queue.fail(c, {**old, "attempts": 3}, "late", worker="old")
            return new, late, late_fail

    new, late, late_fail = arun(go)
    assert new["attempts"] == 2 and late is False and late_fail == "lost"
    assert sql("SELECT status, locked_by FROM ingest_jobs") == [("running", "new")]


def test_reclaim_stale_fails_jobs_that_used_all_attempts():
    async def go(p):
        async with p.connection() as c:
            await queue.enqueue(c, "seed", "crashy", {})
            await c.execute("UPDATE ingest_jobs SET status='running', attempts=3, locked_by='dead', "
                            "locked_at = now() - interval '11 minutes'")
            return await queue.reclaim_stale(c)

    assert arun(go) == 1
    (status, err, lb), = sql("SELECT status, error, locked_by FROM ingest_jobs")
    assert status == "failed" and "crash" in err and lb is None


def test_find_by_sha_with_ref():
    async def go(p):
        fid, _, _ = await save("r", V())
        return fid, await store.find_by_sha(META("r")["sha256"], with_ref=True), await store.find_by_sha("nope", True)

    fid, ref, none = arun(go)
    assert ref == (fid, "upload", META("r")["source_ref"]) and none is None
