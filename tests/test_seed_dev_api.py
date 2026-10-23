"""Block 1: dev-only /api/dev/seed routes, against temp dirs (never the real data)."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from placewise import dev_seed


@pytest.fixture
def client(tmp_path, monkeypatch):
    resumes, public = tmp_path / "resumes", tmp_path / "public"
    resumes.mkdir()
    public.mkdir()
    (tmp_path / "truth").mkdir()
    (tmp_path / "truth" / "candidates.jsonl").write_text('{"secret": true}\n')
    monkeypatch.setattr(dev_seed, "RESUMES", resumes)
    monkeypatch.setattr(dev_seed, "PUBLIC", public)
    monkeypatch.setattr(dev_seed, "SAMPLES", tmp_path / "samples")
    app = FastAPI()
    app.include_router(dev_seed.router)
    return TestClient(app), resumes, public


def _mk(resumes, cid, files: dict):
    d = resumes / cid
    d.mkdir()
    for name, data in files.items():
        (d / name).write_bytes(data)


def test_view_pdf_inline(client):
    c, resumes, _ = client
    _mk(resumes, "C0001", {"A_Resume.pdf": b"%PDF-1.4 fake"})
    r = c.get("/api/dev/seed/files/C0001/view")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"].startswith("inline")


def test_view_docx_uses_preview(client):
    c, resumes, _ = client
    import io, zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", "<x/>")
    _mk(resumes, "C0002", {"B.docx": buf.getvalue(), "_preview.pdf": b"%PDF-preview"})
    r = c.get("/api/dev/seed/files/C0002/view")
    assert r.status_code == 200 and r.content == b"%PDF-preview"


def test_view_corrupt_docx_409(client):
    c, resumes, _ = client
    _mk(resumes, "C0003", {"C.docx": b"PK\x03\x04truncated-garbage"})
    r = c.get("/api/dev/seed/files/C0003/view")
    assert r.status_code == 409 and "corrupt" in r.json()["detail"]
    d = c.get("/api/dev/seed/files/C0003")
    assert d.status_code == 200 and d.headers["content-disposition"].startswith("attachment")


def test_view_txt_without_preview_404(client):
    c, resumes, _ = client
    _mk(resumes, "C0004", {"D.txt": b"plain resume"})
    r = c.get("/api/dev/seed/files/C0004/view")
    assert r.status_code == 404 and "preview" in r.json()["detail"]


def test_download_txt(client):
    c, resumes, _ = client
    _mk(resumes, "C0004", {"D.txt": b"plain resume"})
    r = c.get("/api/dev/seed/files/C0004")
    assert r.status_code == 200 and r.content == b"plain resume" and r.headers["content-type"].startswith("text/plain")


def test_empty_folder_404(client):
    c, resumes, _ = client
    (resumes / "C0005").mkdir()
    assert c.get("/api/dev/seed/files/C0005").status_code == 404
    assert c.get("/api/dev/seed/files/C0005/view").status_code == 404


def test_folder_with_only_preview_404(client):
    c, resumes, _ = client
    _mk(resumes, "C0006", {"_preview.pdf": b"%PDF"})
    assert c.get("/api/dev/seed/files/C0006").status_code == 404


def test_missing_candidate_404(client):
    c, _, _ = client
    assert c.get("/api/dev/seed/files/C9999").status_code == 404


@pytest.mark.parametrize("cid", ["..", "C..", "C0001..", "truth", "C-1", "C 1", "c0001", "C", "C0001x",
                                 "..%2Ftruth", "C..%2F..%2Ftruth", "%2E%2E", "C%00", "C１２"])
def test_bad_ids_are_rejected(client, cid):
    c, resumes, _ = client
    _mk(resumes, "C0001", {"A.pdf": b"%PDF"})
    for path in (f"/api/dev/seed/files/{cid}", f"/api/dev/seed/files/{cid}/view"):
        r = c.get(path)
        assert r.status_code in (400, 404), (path, r.status_code)
        assert b"secret" not in r.content


def test_folder_helper_blocks_traversal_directly(client):
    """Call the guard itself, bypassing URL normalisation."""
    from fastapi import HTTPException
    for cid in ["../truth", "C../../truth", "C0001/../../truth", "/etc/passwd"]:
        with pytest.raises(HTTPException) as e:
            dev_seed._folder(cid)
        assert e.value.status_code in (400, 404)


def test_unicode_digit_id_is_rejected_or_missing(client):
    """str.isdigit() accepts non-ASCII digits like '１２'; make sure that can't escape RESUMES."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as e:
        dev_seed._folder("C１２")
    assert e.value.status_code in (400, 404)


def test_status_and_files_read_public(client):
    c, _, public = client
    (public / "files.json").write_text(json.dumps([{"candidate_id": "C0001"}]))
    (public / "stats.json").write_text("{not json")  # mid-write
    assert c.get("/api/dev/seed/files").json() == [{"candidate_id": "C0001"}]
    s = c.get("/api/dev/seed/status").json()
    assert s["stats"] is None and s["showcase"] == [] and s["progress"] is None


def test_samples_traversal_blocked(client, tmp_path):
    c, _, _ = client
    (tmp_path / "samples").mkdir()
    (tmp_path / "samples" / "ok.pdf").write_bytes(b"%PDF")
    (tmp_path / "outside.pdf").write_bytes(b"%PDF-outside")
    assert c.get("/api/dev/seed/samples").json() == ["ok.pdf"]
    assert c.get("/api/dev/seed/samples/ok.pdf").status_code == 200
    for name in ["..%2Foutside.pdf", "%2E%2E%2Foutside.pdf", "ok.txt"]:
        r = c.get(f"/api/dev/seed/samples/{name}")
        assert r.status_code == 404 and b"outside" not in r.content


def test_routes_only_in_dev(load_app):
    _, dev = load_app("dev")
    assert dev.get("/api/dev/seed/files").status_code == 200
    _, prod = load_app("prod")
    assert prod.get("/api/dev/seed/files").status_code == 404
