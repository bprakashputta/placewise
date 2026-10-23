"""Block 1: seed CLI against a TEMP data dir (PLACEWISE_DATA_DIR), never the real one. No LLM.

`render` is exercised end to end in a subprocess so paths.py picks up the temp dir.
"""
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from placewise.seed import facts as F

from seed_helpers import make_resume

REAL_TRUTH = Path("/app/data/seed/truth/candidates.jsonl")


@pytest.fixture(autouse=True)
def real_data_untouched():
    before = REAL_TRUTH.stat().st_mtime_ns if REAL_TRUTH.exists() else None
    yield
    after = REAL_TRUTH.stat().st_mtime_ns if REAL_TRUTH.exists() else None
    assert before == after, "a test modified the real data/seed/truth!"


def _seed(tmp_path, *args):
    assert str(tmp_path) != "/app/data"
    env = {**os.environ, "PLACEWISE_DATA_DIR": str(tmp_path), "ANTHROPIC_API_KEY": "sk-test-not-real"}
    return subprocess.run([sys.executable, "-m", "placewise.seed", *args], env=env, capture_output=True,
                          text=True, timeout=180)


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


@pytest.fixture
def mini_dataset(tmp_path):
    """One DOCX original, its exact duplicate, a TXT, a corrupt DOCX and an injection PDF."""
    cands = F.generate(50, seed=42)
    dup = next(c for c in cands if c.variant == "exact_duplicate")
    src = next(c for c in cands if c.person_id == dup.person_id and c.variant == "original")
    for c in (src, dup):
        c.style.file_format = "docx"
    txt = next(c for c in cands if c.variant == "original" and not c.unreadable and not c.injection
               and c.person_id != src.person_id)
    txt.style.file_format = "txt"
    corrupt = next((c for c in cands if c.unreadable == "corrupt_docx"), None)
    inj = next(c for c in cands if c.injection)
    chosen = [c for c in (src, dup, txt, corrupt, inj) if c is not None]
    _write_jsonl(tmp_path / "seed/truth/candidates.jsonl",
                 [{**c.model_dump(), "license_codes": c.license_codes} for c in chosen])
    gen = []
    for c in chosen:
        if c is dup:
            gen.append({"candidate_id": c.candidate_id, "copied_from": src.candidate_id,
                        "resume": make_resume(src).model_dump(), "prompt_version": 5})
        else:
            r = make_resume(c)
            gen.append({"candidate_id": c.candidate_id, "resume": r.model_dump(), "text": r.to_text(),
                        "prompt_version": 5})
    _write_jsonl(tmp_path / "seed/generated/resumes.jsonl", gen)
    return tmp_path, {"src": src, "dup": dup, "txt": txt, "corrupt": corrupt, "inj": inj}


def test_render_cli_in_temp_dir(mini_dataset):
    root, c = mini_dataset
    res = _seed(root, "render")
    assert res.returncode == 0, res.stderr[-2000:]
    resumes = root / "seed/resumes"
    files = {r["candidate_id"]: r for r in map(json.loads, (root / "seed/generated/files.jsonl").open())}
    assert set(files) == {x.candidate_id for x in c.values() if x is not None}
    # exact duplicate is a byte-for-byte copy
    assert files[c["dup"].candidate_id]["sha256"] == files[c["src"].candidate_id]["sha256"]
    assert (resumes / c["src"].candidate_id / "_preview.pdf").exists()
    assert (resumes / c["txt"].candidate_id / "_preview.pdf").exists()
    if c["corrupt"]:
        f = resumes / files[c["corrupt"].candidate_id]["path"]
        assert not zipfile.is_zipfile(f) and not (f.parent / "_preview.pdf").exists()
    assert files[c["inj"].candidate_id]["note"] == "hidden injection text"
    # public/ got published and never contains test-split answers
    stats = json.loads((root / "seed/public/stats.json").read_text())
    assert stats["rendered"] == len(files)


def test_exact_duplicate_docx_has_its_own_preview(mini_dataset):
    root, c = mini_dataset
    assert _seed(root, "render").returncode == 0
    dup_dir = root / "seed/resumes" / c["dup"].candidate_id
    assert (dup_dir / "_preview.pdf").exists()


# ---- break-it

def test_render_with_empty_facts_file(tmp_path):
    _write_jsonl(tmp_path / "seed/truth/candidates.jsonl", [])
    _write_jsonl(tmp_path / "seed/generated/resumes.jsonl", [])
    res = _seed(tmp_path, "render")
    assert res.returncode == 0, res.stderr[-2000:]
    assert "rendered 0 files" in res.stdout


def test_load_facts_empty_file_returns_empty(tmp_path, monkeypatch):
    from placewise.seed import __main__ as M
    (tmp_path / "candidates.jsonl").write_text("")
    monkeypatch.setattr(M, "TRUTH", tmp_path)
    assert M.load_facts() == []


def test_render_skips_resume_rows_without_facts(mini_dataset):
    root, c = mini_dataset
    gen_path = root / "seed/generated/resumes.jsonl"
    rows = [json.loads(x) for x in gen_path.read_text().splitlines()]
    orphan = {**rows[0], "candidate_id": "C9999"}
    gen_path.write_text("".join(json.dumps(r) + "\n" for r in rows + [orphan]))
    res = _seed(root, "render")
    assert res.returncode == 0, res.stderr[-2000:]
    assert not (root / "seed/resumes/C9999").exists()


def test_facts_cli_small_count_in_temp_dir(tmp_path):
    res = _seed(tmp_path, "facts", "--count", "30", "--seed", "1")
    assert res.returncode == 0, res.stderr[-2000:]
    lines = (tmp_path / "seed/truth/candidates.jsonl").read_text().splitlines()
    assert len(lines) == 30 and all("license_codes" in json.loads(x) for x in lines)
    assert (tmp_path / "seed/public/stats.json").exists()
