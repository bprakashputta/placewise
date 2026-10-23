"""QA (Blocks 3-6): route protection on the REAL app, API validation, spend-cap 429s, decision
endpoint, match-run filter relaxation and dashboard stats shape.

No database, network or LLM: the pool and the paid calls are faked. Tests marked xfail(strict=True)
document bugs found in QA; they start "passing" (and so fail the suite) once the bug is fixed, as a
reminder to drop the marker.
"""
import asyncio

import pytest
from fastapi.testclient import TestClient
from itsdangerous import URLSafeTimedSerializer

from placewise import auth
from placewise.ingest.spend import SpendCapReached

ADMIN = {"id": 1, "username": "admin", "display_name": "Demo Admin", "role": "admin"}
RECRUITER = {"id": 2, "username": "recruiter", "display_name": "Demo Recruiter", "role": "recruiter"}

# Routes that must answer WITHOUT a session (everything else under /api needs one).
PUBLIC = {("GET", "/api/health"), ("POST", "/api/auth/login"), ("POST", "/api/auth/logout")}
ADMIN_ONLY_PREFIXES = ("/api/admin/", "/api/dev/")
ADMIN_ONLY_EXACT = {("POST", "/api/ingest/jobs/retry-failed")}


def _api_routes(client) -> list[tuple[str, str]]:
    spec = client.get("/openapi.json").json()
    out = []
    for path, ops in spec["paths"].items():
        for method in ops:
            if path.startswith("/api/"):
                out.append((method.upper(), path))
    return sorted(out)


def _concrete(path: str) -> str:
    return (path.replace("{name}", "x").replace("{person_id}", "1").replace("{resume_file_id}", "1")
            .replace("{job_id}", "1").replace("{match_id}", "1").replace("{candidate_id}", "1"))


@pytest.fixture
def app_client(load_app):
    main, client = load_app("dev")
    yield main, client
    main.app.dependency_overrides.clear()


# ----------------------------------------------------------------------------- auth on every route

def test_every_api_route_requires_a_session(app_client):
    main, client = app_client
    routes = _api_routes(client)
    assert len(routes) >= 30, routes          # the enumeration itself works (lazy routers included)
    for method, path in routes:
        if (method, path) in PUBLIC:
            continue
        r = client.request(method, _concrete(path))
        assert r.status_code == 401, f"{method} {path} -> {r.status_code}"


def test_recruiter_gets_403_on_every_admin_route(app_client):
    main, client = app_client
    main.app.dependency_overrides[auth.current_user] = lambda: RECRUITER
    admin_routes = [(m, p) for m, p in _api_routes(client)
                    if p.startswith(ADMIN_ONLY_PREFIXES) or (m, p) in ADMIN_ONLY_EXACT]
    assert ("GET", "/api/admin/costs") in admin_routes and ("POST", "/api/dev/ingest/reset") in admin_routes
    for method, path in admin_routes:
        r = client.request(method, _concrete(path))
        assert r.status_code == 403, f"{method} {path} -> {r.status_code}"


def test_cookie_signed_with_another_key_is_401_on_the_real_app(app_client):
    _, client = app_client
    forged = URLSafeTimedSerializer("attacker-key", salt="placewise-session").dumps({"uid": 1, "role": "admin"})
    client.cookies.set(auth.COOKIE, forged)
    assert client.get("/api/admin/costs").status_code == 401
    assert client.get("/api/candidates").status_code == 401
    client.cookies.set(auth.COOKIE, "not.a.token")
    assert client.get("/api/auth/me").status_code == 401


def test_login_credentials_in_query_string_are_not_accepted(app_client):
    _, client = app_client
    assert client.get("/api/auth/login?username=admin&password=x").status_code == 405
    assert client.post("/api/auth/login?username=admin&password=x").status_code == 422


def _login_app(monkeypatch):
    from fastapi import FastAPI
    from test_auth import FakePool

    user = {"id": 1, "username": "admin", "display_name": "A", "role": "admin",
            "password_hash": auth.hash_password("right")}
    monkeypatch.setattr(auth, "pool", lambda: FakePool({"by_name": {"admin": user}, "by_id": {1: user}}))
    auth._failures.clear()
    a = FastAPI()
    a.include_router(auth.router)
    return TestClient(a)


def test_rate_limit_cannot_be_bypassed_by_spoofing_x_forwarded_for(monkeypatch):
    """Regression for the QA finding: the client-controlled (leftmost) XFF entries must not pick the
    rate-limit bucket. Next.js appends the real peer as the RIGHTMOST hop. Usernames vary so only the
    IP bucket can trigger the 429."""
    c = _login_app(monkeypatch)
    proxy_hop = "172.18.0.9"
    codes = [c.post("/api/auth/login", json={"username": f"ghost{i}", "password": "x"},
                    headers={"X-Forwarded-For": f"203.0.113.{i}, {proxy_hop}"}).status_code for i in range(6)]
    r = c.post("/api/auth/login", json={"username": "ghost-new", "password": "x"},
               headers={"X-Forwarded-For": f"198.51.100.7, {proxy_hop}"})
    auth._failures.clear()
    assert codes == [401] * 5 + [429] and r.status_code == 429


def test_rate_limit_per_username_across_ips(monkeypatch):
    c = _login_app(monkeypatch)
    codes = [c.post("/api/auth/login", json={"username": "admin", "password": "wrong"},
                    headers={"X-Forwarded-For": f"203.0.113.{i}"}).status_code for i in range(6)]
    locked = c.post("/api/auth/login", json={"username": "admin", "password": "right"},
                    headers={"X-Forwarded-For": "198.51.100.1"}).status_code
    auth._failures.clear()
    assert codes == [401] * 5 + [429] and locked == 429


# ----------------------------------------------------------------------------- fake DB

class _Cur:
    def __init__(self, rows=None, one=None):
        self.rows, self.one = rows or [], one

    async def fetchone(self):
        return self.one

    async def fetchall(self):
        return self.rows

    async def execute(self, sql, params=None):
        return self


class _Conn:
    def __init__(self, handler):
        self.handler, self.calls = handler, []

    async def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return self.handler(sql, params)

    def cursor(self, row_factory=None):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _Pool:
    def __init__(self, handler):
        self.conn = _Conn(handler)

    def connection(self):
        return self.conn


# ----------------------------------------------------------------------------- matching API

def test_decision_body_validation(app_client):
    main, client = app_client
    main.app.dependency_overrides[auth.current_user] = lambda: RECRUITER
    for bad in ({}, {"status": "maybe"}, {"status": "APPROVED"}, {"status": "approved; drop"}, {"status": None}):
        assert client.post("/api/matches/1/decision", json=bad).status_code == 422, bad
    assert client.post("/api/matches/abc/decision", json={"status": "approved"}).status_code == 422


def test_decision_updates_and_404s(app_client, monkeypatch):
    from placewise import matching_api

    main, client = app_client
    main.app.dependency_overrides[auth.current_user] = lambda: RECRUITER
    pool = _Pool(lambda sql, p: _Cur(one=(p[-1],) if p[-1] == 7 else None))   # match id is the last param
    monkeypatch.setattr(matching_api, "pool", lambda: pool)
    for status in ("approved", "rejected", "proposed"):          # approve, reject, undo
        r = client.post("/api/matches/7/decision", json={"status": status})
        assert r.status_code == 200 and r.json() == {"id": 7, "status": status}
    sql, params = pool.conn.calls[-1]
    # last call was the undo ('proposed'): decided_by/decided_at are cleared via CASE on the status
    assert "UPDATE matches" in sql and params == ("proposed", "proposed", RECRUITER["id"], "proposed", 7)
    assert client.post("/api/matches/8/decision", json={"status": "approved"}).status_code == 404


def test_job_order_notes_validation_and_spend_cap(app_client, monkeypatch):
    from placewise import matching_api

    main, client = app_client
    main.app.dependency_overrides[auth.current_user] = lambda: RECRUITER
    assert client.post("/api/job-orders", json={"notes": "too short"}).status_code == 422
    assert client.post("/api/job-orders", json={"notes": "x" * 6001}).status_code == 422

    async def capped(notes):
        raise SpendCapReached("daily LLM spend cap reached ($25.00 of $25.00)")

    monkeypatch.setattr(matching_api, "extract_job", capped)
    r = client.post("/api/job-orders", json={"notes": "Need a Texas PE civil engineer in DFW, 8+ years."})
    assert r.status_code == 429 and "spend cap" in r.json()["detail"]


def test_start_match_404_and_429(app_client, monkeypatch):
    from placewise import matching_api

    main, client = app_client
    main.app.dependency_overrides[auth.current_user] = lambda: RECRUITER

    async def missing(job_id, user_id):
        raise ValueError("job order not found")

    monkeypatch.setattr(matching_api, "run_match", missing)
    assert client.post("/api/job-orders/999/match").status_code == 404

    async def capped(job_id, user_id):
        raise SpendCapReached("cap")

    monkeypatch.setattr(matching_api, "run_match", capped)
    assert client.post("/api/job-orders/1/match").status_code == 429


# ----------------------------------------------------------------------------- RAG API

def test_ask_body_validation(app_client, monkeypatch):
    from placewise import rag_api

    main, client = app_client
    main.app.dependency_overrides[auth.current_user] = lambda: RECRUITER

    async def never(*a, **k):
        raise AssertionError("invalid bodies must not reach the LLM")

    monkeypatch.setattr(rag_api, "run_ask", never)
    for bad in ({}, {"question": "ab"}, {"question": "a" * 2001},
                {"question": "civil engineers", "filters": {"min_years": "lots"}},
                {"question": "civil engineers", "filters": {"license_codes": "PE:TX"}}):
        assert client.post("/api/ask", json=bad).status_code == 422, bad


def test_ask_passes_filters_and_returns_429_at_spend_cap(app_client, monkeypatch):
    from placewise import rag_api

    main, client = app_client
    main.app.dependency_overrides[auth.current_user] = lambda: RECRUITER
    seen = {}

    async def fake_ask(question, filters):
        seen.update(question=question, filters=filters)
        return {"question": question, "answer": "ok", "citations": []}

    monkeypatch.setattr(rag_api, "run_ask", fake_ask)
    r = client.post("/api/ask", json={"question": "  Texas PE in DFW  ", "filters": {"metro": "DFW",
                                                                                      "license_codes": ["PE:TX"]}})
    assert r.status_code == 200 and seen["question"] == "Texas PE in DFW"
    assert seen["filters"]["metro"] == "DFW" and seen["filters"]["license_codes"] == ["PE:TX"]

    async def capped(question, filters):
        raise SpendCapReached("daily LLM spend cap reached ($25.00 of $25.00); will retry later")

    monkeypatch.setattr(rag_api, "run_ask", capped)
    r = client.post("/api/ask", json={"question": "Who has HEC-RAS?"})
    assert r.status_code == 429 and "spend cap" in r.json()["detail"]


def test_spend_check_raises_at_or_over_cap(monkeypatch):
    from placewise.config import get_settings
    from placewise.ingest import spend

    cap = get_settings().daily_llm_spend_cap_usd
    for spent, raises in ((cap - 0.01, False), (cap, True), (cap + 3, True)):
        monkeypatch.setattr(spend, "pool", lambda s=spent: _Pool(lambda sql, p: _Cur(one=(s,))))
        if raises:
            with pytest.raises(SpendCapReached):
                asyncio.run(spend.check())
        else:
            asyncio.run(spend.check())


def test_whitespace_only_question_is_rejected(app_client, monkeypatch):
    from placewise import rag_api

    main, client = app_client
    main.app.dependency_overrides[auth.current_user] = lambda: RECRUITER

    async def fake_ask(question, filters):
        return {"question": question}

    monkeypatch.setattr(rag_api, "run_ask", fake_ask)
    assert client.post("/api/ask", json={"question": "     "}).status_code == 422


def test_search_with_empty_query_does_not_hit_the_embedder(app_client, monkeypatch):
    from placewise import rag_api

    main, client = app_client
    main.app.dependency_overrides[auth.current_user] = lambda: RECRUITER

    async def voyage_like(q, f, k=60):
        if not q.strip():
            raise ValueError("Input cannot contain empty strings or empty lists")
        return []

    monkeypatch.setattr(rag_api, "hybrid", voyage_like)
    for q in ("", " "):
        r = client.get(f"/api/search?q={q}")
        assert r.status_code in (200, 422), (q, r.status_code)


# ----------------------------------------------------------------------------- run.relaxed

def _spec_dict():
    return {"title": "Drainage Engineer", "metro": "DFW", "discipline": "civil", "min_years": 6,
            "requirements": [
                {"text": "Texas PE", "kind": "license", "priority": "must", "key": "PE", "state": "TX"},
                {"text": "6+ years", "kind": "years", "priority": "must", "value": "6"},
                {"text": "HEC-RAS", "kind": "software", "priority": "nice"}]}


def _run_with_counts(monkeypatch, counts_by_label):
    from placewise.matching import engine

    spec = _spec_dict()
    labels = [lbl for lbl, _ in engine.hard_filters(engine.JobSpec.model_validate(spec))]
    order = iter(labels)

    async def fake_count(f):
        return counts_by_label[next(order)]

    inserted = {}

    def handler(sql, params):
        if sql.lstrip().startswith("SELECT spec"):
            return _Cur(one=(spec,))
        if "INSERT INTO match_runs" in sql:
            inserted["filters"], inserted["relaxed"] = params[2], params[3]
        return _Cur()

    async def no_finish(*a, **k):
        return None

    monkeypatch.setattr(engine, "pool", lambda: _Pool(handler))
    monkeypatch.setattr(engine, "_count", fake_count)
    monkeypatch.setattr(engine, "_finish", no_finish)
    monkeypatch.setattr(engine, "spend_check", no_finish)

    async def go():
        run_id = await engine.run_match(1, 2)
        await asyncio.sleep(0)
        return run_id

    run_id = asyncio.run(go())
    assert run_id.startswith("m-")
    import json
    return labels, inserted["relaxed"], json.loads(inserted["filters"])


def test_run_not_relaxed_when_strict_pool_is_big_enough(monkeypatch):
    labels, relaxed, f = _run_with_counts(monkeypatch, {"strict": 20, "years": 30, "metro": 40, "license": 99})
    assert labels == ["strict", "years", "metro", "license"]
    assert relaxed == [] and f["license_codes"] == ["PE:TX"] and f["metro"] == "DFW" and f["min_years"] == 5


def test_run_relaxes_step_by_step_until_min_pool(monkeypatch):
    _, relaxed, f = _run_with_counts(monkeypatch, {"strict": 1, "years": 3, "metro": 7, "license": 99})
    assert relaxed == ["years", "metro"]
    assert f["min_years"] is None and f["metro"] is None and f["license_codes"] == ["PE:TX"]


def test_run_relaxes_everything_when_pool_stays_small(monkeypatch):
    _, relaxed, f = _run_with_counts(monkeypatch, {"strict": 0, "years": 0, "metro": 1, "license": 2})
    assert relaxed == ["years", "metro", "license"]
    assert f["license_codes"] == [] and f["discipline"] == "civil"   # discipline is never relaxed


def test_run_match_unknown_job_raises_value_error(monkeypatch):
    from placewise.matching import engine

    monkeypatch.setattr(engine, "pool", lambda: _Pool(lambda sql, p: _Cur(one=None)))
    with pytest.raises(ValueError):
        asyncio.run(engine.run_match(999))


def test_license_filter_not_dropped_for_words_containing_or():
    from placewise.matching.engine import hard_filters
    from placewise.matching.schema import JobSpec, Requirement

    spec = JobSpec(title="Structural PE", discipline="structural", requirements=[
        Requirement(text="Texas PE required for stamping drawings", kind="license", priority="must",
                    key="PE", state="TX")])
    assert hard_filters(spec)[0][1].license_codes == ["PE:TX"]


# ----------------------------------------------------------------------------- stats shape

def test_stats_shape_with_faked_pool(app_client, monkeypatch):
    from placewise import stats_api

    main, client = app_client
    main.app.dependency_overrides[auth.current_user] = lambda: RECRUITER

    def handler(sql, params):
        if "GROUP BY" in sql and "ingest_jobs" in sql:
            return _Cur(rows=[("done", 586), ("needs_attention", 8)])
        if "GROUP BY" in sql and "quality" in sql:
            return _Cur(rows=[("polished", 508), ("flawed", 54)])
        if "sum(cost_usd)" in sql:
            return _Cur(one=(1.23456,))
        return _Cur(one=(7,))

    monkeypatch.setattr(stats_api, "pool", lambda: _Pool(handler))
    r = client.get("/api/stats")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"candidates", "needs_attention", "files_processed", "ingest_jobs", "by_quality",
                         "ai_spend_today_usd", "ai_spend_total_usd", "spend_cap_usd", "open_job_orders",
                         "shortlists_to_review"}
    assert body["ingest_jobs"] == {"done": 586, "needs_attention": 8}
    assert body["by_quality"] == {"polished": 508, "flawed": 54}
    assert body["ai_spend_today_usd"] == 1.2346 and isinstance(body["spend_cap_usd"], float)
    assert all(isinstance(body[k], int) for k in ("candidates", "needs_attention", "files_processed",
                                                  "open_job_orders", "shortlists_to_review"))


def test_admin_costs_is_403_for_recruiter_and_shaped_for_admin(app_client, monkeypatch):
    from placewise import stats_api

    main, client = app_client
    main.app.dependency_overrides[auth.current_user] = lambda: RECRUITER
    assert client.get("/api/admin/costs").status_code == 403
    main.app.dependency_overrides[auth.current_user] = lambda: ADMIN

    def handler(sql, params):
        return _Cur()

    class CostConn(_Conn):
        n = 0

        async def execute(self, sql, params=None):
            self.calls.append(sql)
            return self

        async def fetchall(self):
            return [{"day": "2026-10-23", "calls": 3, "cost_usd": 0.1}] if len(self.calls) == 1 else []

        async def fetchone(self):
            return {"s": 0.1}

    pool = _Pool(handler)
    pool.conn = CostConn(handler)
    monkeypatch.setattr(stats_api, "pool", lambda: pool)
    body = client.get("/api/admin/costs").json()
    assert set(body) == {"spend_cap_usd", "spent_today_usd", "by_day", "by_step_model"}
    assert body["by_day"][0]["day"] == "2026-10-23"


# ----------------------------------------------------------------------------- reviewer-fix regressions

def test_start_match_409_when_a_run_is_in_progress(app_client, monkeypatch):
    from placewise import matching_api
    from placewise.matching.engine import RunInProgress

    main, client = app_client
    main.app.dependency_overrides[auth.current_user] = lambda: RECRUITER

    async def busy(job_id, user_id):
        raise RunInProgress("a match is already running for this job order")

    monkeypatch.setattr(matching_api, "run_match", busy)
    r = client.post("/api/job-orders/1/match")
    assert r.status_code == 409 and "already running" in r.json()["detail"]


def _engine_pool(monkeypatch, running: bool):
    from placewise.matching import engine

    spec, inserts = _spec_dict(), []

    def handler(sql, params):
        if sql.lstrip().startswith("SELECT spec"):
            return _Cur(one=(spec,))
        if "status='running'" in sql and sql.lstrip().startswith("SELECT"):
            return _Cur(one=("m-busy",) if running else None)
        if "INSERT INTO match_runs" in sql:
            inserts.append(params)
        return _Cur()

    monkeypatch.setattr(engine, "pool", lambda: _Pool(handler))
    return engine, inserts


def test_run_match_refuses_second_concurrent_run(monkeypatch):
    engine, inserts = _engine_pool(monkeypatch, running=True)

    async def ok():
        return None

    monkeypatch.setattr(engine, "spend_check", ok)
    with pytest.raises(engine.RunInProgress):
        asyncio.run(engine.run_match(1, 2))
    assert inserts == []


def test_run_match_checks_spend_cap_before_creating_a_run(monkeypatch):
    engine, inserts = _engine_pool(monkeypatch, running=False)

    async def capped():
        raise SpendCapReached("cap")

    monkeypatch.setattr(engine, "spend_check", capped)
    with pytest.raises(SpendCapReached):
        asyncio.run(engine.run_match(1, 2))
    assert inserts == []          # no orphan 'running' row when the cap is hit


def test_rate_limit_ignores_client_supplied_cf_connecting_ip(monkeypatch):
    c = _login_app(monkeypatch)
    codes = [c.post("/api/auth/login", json={"username": f"spray{i}", "password": "x"},
                    headers={"CF-Connecting-IP": f"203.0.113.{i}"}).status_code for i in range(6)]
    auth._failures.clear()
    assert codes[-1] == 429
