"""Block 2: /api/candidates/upload validation with the DB pool and queue faked (no database)."""
import contextlib
import hashlib
import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from placewise import candidates_api

GOOD_TXT = ("Jordan Sample\nSenior Civil Engineer, Dallas TX\nAcme Civil 2016 - Present\n" * 5).encode()


@pytest.fixture
def client(tmp_path, monkeypatch):
    uploads = tmp_path / "storage" / "uploads"
    monkeypatch.setattr(candidates_api, "UPLOADS", uploads)
    seen: dict = {}

    class FakePool:
        @contextlib.asynccontextmanager
        async def connection(self):
            yield object()

    async def enqueue(conn, source, ref, payload):
        if (source, ref) in seen:
            return None
        seen[(source, ref)] = payload
        return len(seen)

    monkeypatch.setattr(candidates_api, "pool", lambda: FakePool())
    monkeypatch.setattr(candidates_api.queue, "enqueue", enqueue)
    app = FastAPI()
    app.include_router(candidates_api.router)
    return TestClient(app, raise_server_exceptions=False), uploads, seen


def post(c, data: bytes, name="resume.txt", ctype="text/plain"):
    return c.post("/api/candidates/upload", files={"file": (name, io.BytesIO(data), ctype)})


def test_valid_txt_is_queued_and_saved(client):
    c, uploads, seen = client
    r = post(c, GOOD_TXT)
    sha = hashlib.sha256(GOOD_TXT).hexdigest()
    assert r.status_code == 200
    body = r.json()
    assert body["queued"] is True and body["sha256"] == sha and body["message"] == "Queued for processing"
    assert (uploads / sha / "resume.txt").read_bytes() == GOOD_TXT
    assert seen[("upload", sha)] == {"storage_path": f"uploads/{sha}/resume.txt"}


def test_identical_resubmission_says_already_submitted(client):
    c, _, _ = client
    post(c, GOOD_TXT)
    r = post(c, GOOD_TXT, name="renamed.txt")
    assert r.status_code == 200
    assert r.json()["queued"] is False and r.json()["job_id"] is None
    assert r.json()["message"] == "This exact file was already submitted"


def test_too_large_is_413(client):
    c, uploads, seen = client
    r = post(c, b"a" * (11 * 1024 * 1024))
    assert r.status_code == 413 and not seen and not uploads.exists()


def test_exactly_10mb_is_accepted(client):
    c, _, _ = client
    assert post(c, b"a" * (10 * 1024 * 1024)).status_code == 200


def test_binary_blob_is_415(client):
    c, _, seen = client
    r = post(c, bytes(range(128, 256)) * 40, name="resume.pdf", ctype="application/pdf")
    assert r.status_code == 415 and not seen


def test_type_is_sniffed_not_trusted_from_extension(client):
    c, uploads, seen = client
    pdf = b"%PDF-1.4\n" + b"x" * 100
    r = post(c, pdf, name="resume.txt", ctype="text/plain")
    assert r.status_code == 200  # accepted as a PDF by content; the parser decides if it's readable


def test_empty_file_is_rejected(client):
    c, _, seen = client
    r = post(c, b"")
    assert r.status_code in (400, 415) and not seen


@pytest.mark.parametrize("name,expected", [
    ("../../etc/passwd.txt", "passwd.txt"),
    ("..\\..\\win.txt", "_.._win.txt"),
    ("/abs/path/cv.txt", "cv.txt"),
    ("my résumé (final);rm -rf.txt", "my r_sum_ _final__rm -rf.txt"),
    ("x" * 300 + ".txt", "x" * 110 + ".txt"),  # long names are trimmed but keep their extension
    ("..", "resume.txt"),
    ("a/..", "resume.txt"),
    (".", "resume.txt"),
    ("...hidden.txt", "hidden.txt"),
    ("noext", "resume.txt"),
])
def test_filename_is_sanitized_and_stays_in_upload_folder(client, name, expected):
    c, uploads, seen = client
    data = GOOD_TXT + name.encode()  # unique bytes per case
    r = post(c, data, name=name)
    assert r.status_code == 200, r.text
    sha = r.json()["sha256"]
    stored = list((uploads / sha).iterdir())
    assert [p.name for p in stored] == [expected]
    assert stored[0].resolve().parent == (uploads / sha).resolve()
    assert seen[("upload", sha)]["storage_path"] == f"uploads/{sha}/{expected}"


def test_latin1_txt_resume_is_accepted(client):
    c, _, _ = client
    r = post(c, ("José Martínez – Résumé\n" + "Civil engineer 2015-2024. " * 10).encode("cp1252"))
    assert r.status_code == 200


def test_utf8_txt_with_multibyte_char_at_4000_boundary_is_accepted(client):
    c, _, _ = client
    data = b"a" * 3999 + "é".encode() + b" Civil engineer 2015-2024." * 5
    data.decode("utf-8")  # genuinely valid UTF-8
    assert post(c, data).status_code == 200
