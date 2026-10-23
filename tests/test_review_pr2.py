"""PR #2 review: the matching evidence rule, the database-enforced single run, Voyage logging and the
spend cap on smart search."""
import asyncio

import psycopg
import pytest

from placewise import auth
from placewise.ingest.spend import SpendCapReached
from placewise.matching import engine
from placewise.matching.schema import JobSpec, MatchAssessment, RequirementVerdict

RECRUITER = {"id": 2, "username": "recruiter", "display_name": "Demo Recruiter", "role": "recruiter"}

SPEC = JobSpec.model_validate({
    "title": "Drainage Engineer", "metro": "Houston", "discipline": "civil", "requirements": [
        {"text": "Texas PE license", "kind": "license", "priority": "must", "key": "PE", "state": "TX"},
        {"text": "HEC-RAS modeling", "kind": "software", "priority": "must", "key": "HEC-RAS"},
        {"text": "Stormwater design", "kind": "specialty", "priority": "must"},
        {"text": "Civil 3D", "kind": "software", "priority": "nice"},
        {"text": "Floodplain permitting", "kind": "specialty", "priority": "nice"}]})
PROF = {"person_id": 1, "resume_file_id": 10, "discipline": "civil", "metro": "Houston", "years_experience": 8,
        "license_codes": ["PE:TX"], "open_to_relocation": False,
        "blind_text": "Built HEC-RAS 2D models for the Brays Bayou channel — drainage and detention design. Civil 3D."}


def _run_assess(monkeypatch, verdicts):
    async def no_spend():
        return None

    async def no_log(*a, **k):
        return None

    class FakeModel:
        async def ainvoke(self, *a, **k):
            return {"parsed": MatchAssessment(verdicts=verdicts, flags=[], summary="s"), "raw": None}

    monkeypatch.setattr(engine, "spend_check", no_spend)
    monkeypatch.setattr(engine, "log_call", no_log)
    monkeypatch.setattr(engine, "_structured", lambda *a, **k: FakeModel())
    monkeypatch.setattr(engine, "_cost", lambda *a, **k: (0.0, 0, 0))
    return asyncio.run(engine.assess(SPEC, PROF, asyncio.Semaphore(1), "m-test"))


def _v(out, req):
    return next(v for v in out["verdicts"] if v["requirement"] == req)


def test_evidence_rule_downgrades_unsupported_and_keeps_real_quotes(monkeypatch):
    out = _run_assess(monkeypatch, [
        # real quote, differs only by whitespace and dash style → kept
        RequirementVerdict(requirement="HEC-RAS modeling", verdict="met",
                           evidence="Built  HEC-RAS 2D models for the Brays Bayou channel - drainage"),
        # no quote → unknown
        RequirementVerdict(requirement="Stormwater design", verdict="met", evidence=None),
        # quote not in the profile → unknown, evidence removed
        RequirementVerdict(requirement="Floodplain permitting", verdict="partial",
                           evidence="Managed FEMA floodplain permits for 30 subdivisions"),
        # too short to count, even though it's in the text → unknown
        RequirementVerdict(requirement="Civil 3D", verdict="met", evidence="Civil 3D"),
        # the LLM tries to override a code verdict (license) → ignored
        RequirementVerdict(requirement="Texas PE license", verdict="not_met", evidence=None),
    ])
    assert _v(out, "HEC-RAS modeling")["verdict"] == "met"
    assert _v(out, "Stormwater design")["verdict"] == "unknown"
    assert _v(out, "Floodplain permitting")["verdict"] == "unknown" and _v(out, "Floodplain permitting")["evidence"] is None
    assert _v(out, "Civil 3D")["verdict"] == "unknown"
    lic = [v for v in out["verdicts"] if v["requirement"] == "Texas PE license"]
    assert len(lic) == 1 and lic[0]["verdict"] == "met"          # the code verdict stands, the LLM's is dropped
    assert "unsupported verdict downgraded" in out["flags"] and "unverified evidence removed" in out["flags"]


def test_concurrent_run_is_refused_by_the_database(monkeypatch):
    class Conn:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

        async def execute(self, sql, params=None):
            if sql.startswith("SELECT spec"):
                class C:
                    async def fetchone(self_inner): return (SPEC.model_dump(),)
                return C()
            if sql.startswith("UPDATE match_runs SET status='failed'"):   # stale sweep (nothing stale here)
                return None
            if sql.startswith("INSERT INTO match_runs"):
                raise psycopg.errors.UniqueViolation("duplicate key value violates match_runs_one_running")
            raise AssertionError(sql)

    class Pool:
        def connection(self): return Conn()

    async def no_spend():
        return None

    async def count(f):
        return 99

    monkeypatch.setattr(engine, "pool", lambda: Pool())
    monkeypatch.setattr(engine, "spend_check", no_spend)
    monkeypatch.setattr(engine, "_count", count)
    with pytest.raises(engine.RunInProgress):
        asyncio.run(engine.run_match(3, 1))


def test_rerank_is_bounded_and_logged(monkeypatch):
    from placewise.rag import rerank as rr
    from placewise.rag.retrieve import Hit
    logged = {}

    class Res:
        total_tokens = 1234
        results = [type("R", (), {"index": 1, "relevance_score": 0.9})()]

    class Client:
        def __init__(self, **kw):
            logged["client_kw"] = kw

        async def rerank(self, q, docs, model, top_k):
            return Res()

    async def log(run_ref, step, model, pv, inp, out, ms, cost, status, error=None):
        logged.update(run_ref=run_ref, step=step, inp=inp)

    monkeypatch.setattr(rr.voyageai, "AsyncClient", Client)
    monkeypatch.setattr(rr, "log_call", log)
    monkeypatch.setattr(rr, "_client", None)
    hits = [Hit(1, 1, 1, "job", "a"), Hit(2, 2, 2, "job", "b")]
    out = asyncio.run(rr.rerank("q", hits, run_ref="ask"))
    assert out[0].chunk_id == 2 and out[0].rerank == 0.9
    assert logged["client_kw"] == {"timeout": 15, "max_retries": 2}
    assert logged["step"] == "voyage.rerank" and logged["inp"] == 1234 and logged["run_ref"] == "ask"


def test_smart_search_respects_the_spend_cap(load_app, monkeypatch):
    from placewise import rag_api
    main, client = load_app("dev")
    main.app.dependency_overrides[auth.current_user] = lambda: RECRUITER

    async def capped():
        raise SpendCapReached("cap")

    async def never(*a, **k):
        raise AssertionError("must not call Voyage when capped")

    monkeypatch.setattr(rag_api, "spend_check", capped)
    monkeypatch.setattr(rag_api, "hybrid", never)
    try:
        assert client.get("/api/search", params={"q": "drainage engineer"}).status_code == 429
    finally:
        main.app.dependency_overrides.clear()


def test_verdicts_with_changed_requirement_text_are_flagged_not_silently_dropped(monkeypatch):
    out = _run_assess(monkeypatch, [
        RequirementVerdict(requirement="HEC-RAS modelling experience", verdict="met",    # text changed by the model
                           evidence="Built HEC-RAS 2D models for the Brays Bayou channel"),
    ])
    assert _v(out, "Texas PE license")["verdict"] == "met"
    assert not any(v["requirement"] == "HEC-RAS modelling experience" for v in out["verdicts"])
    assert "1 AI verdict(s) ignored: requirement text didn't match the job order" in out["flags"]


def test_duplicate_verdicts_keep_only_the_first(monkeypatch):
    q = "Built HEC-RAS 2D models for the Brays Bayou channel"
    out = _run_assess(monkeypatch, [
        RequirementVerdict(requirement="HEC-RAS modeling", verdict="met", evidence=q),
        RequirementVerdict(requirement="HEC-RAS modeling", verdict="not_met", evidence=None),
    ])
    rows = [v for v in out["verdicts"] if v["requirement"] == "HEC-RAS modeling"]
    assert len(rows) == 1 and rows[0]["verdict"] == "met"
