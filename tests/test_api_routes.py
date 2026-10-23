"""Route-level tests: /api/health, /livez, and dev-only routes in dev vs prod."""
import asyncio

from conftest import OK_DB, OK_LS

DB_DOWN = {"ok": False, "detail": "cannot connect (OperationalError)"}
LS_DOWN = {"ok": False, "detail": "cannot reach LangSmith (ConnectError)"}


def test_health_all_ok(load_app, mock_checks):
    main, client = load_app("dev")
    mock_checks(main)
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert set(body["checks"]) == {"api", "db", "langsmith"}
    assert all(c["ok"] for c in body["checks"].values())
    assert body["checks"]["db"]["detail"] == OK_DB["detail"]  # dev shows details


def test_health_503_when_db_down(load_app, mock_checks):
    main, client = load_app("dev")
    mock_checks(main, db=DB_DOWN)
    r = client.get("/api/health")
    assert r.status_code == 503
    body = r.json()
    assert body["ok"] is False
    assert body["checks"]["db"] == DB_DOWN
    assert body["checks"]["langsmith"]["ok"] is True


def test_health_503_when_langsmith_down(load_app, mock_checks):
    main, client = load_app("dev")
    mock_checks(main, langsmith=LS_DOWN)
    r = client.get("/api/health")
    assert r.status_code == 503
    assert r.json()["checks"]["langsmith"] == LS_DOWN
    assert r.json()["checks"]["db"]["ok"] is True


def test_health_503_when_langsmith_check_raises_timeout(load_app, mock_checks):
    """Even if check_langsmith itself raises TimeoutError, the route returns a body."""
    main, client = load_app("dev")
    mock_checks(main, langsmith=asyncio.TimeoutError())
    r = client.get("/api/health")
    assert r.status_code == 503
    assert r.json()["checks"]["langsmith"] == {"ok": False, "detail": "timed out"}


def test_health_503_when_langsmith_sync_call_times_out(load_app, monkeypatch):
    """End to end through the real check_langsmith: a slow LangSmith call times out."""
    import time

    from placewise import health

    main, client = load_app("dev")

    async def fake_db():
        return OK_DB

    monkeypatch.setattr(main, "check_db", fake_db)
    monkeypatch.setattr(health, "_check_langsmith_sync", lambda: time.sleep(0.5) or OK_LS)
    real_wait_for = asyncio.wait_for
    monkeypatch.setattr(health.asyncio, "wait_for", lambda aw, timeout: real_wait_for(aw, 0.05))
    r = client.get("/api/health")
    assert r.status_code == 503
    assert r.json()["checks"]["langsmith"] == {"ok": False, "detail": "timed out"}


def test_livez_does_not_touch_db_or_langsmith(load_app, monkeypatch):
    main, client = load_app("dev")

    async def boom():
        raise AssertionError("livez must not run health checks")

    monkeypatch.setattr(main, "check_db", boom)
    monkeypatch.setattr(main, "check_langsmith", boom)

    def no_pool():
        raise AssertionError("livez must not use the db pool")

    from placewise import db, health

    monkeypatch.setattr(db, "pool", no_pool)
    monkeypatch.setattr(health, "pool", no_pool)
    r = client.get("/livez")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_dev_mode_exposes_docs_openapi_and_trace(load_app, monkeypatch):
    main, client = load_app("dev")
    assert main.DEV is True
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    # Don't send a real trace: stub the traced function.
    monkeypatch.setattr(main, "_trace_check", lambda: {"message": "stub"})
    r = client.post("/dev/trace")
    assert r.status_code == 200
    assert r.json() == {"message": "stub"}


def test_prod_mode_disables_docs_openapi_and_trace(load_app):
    main, client = load_app("prod")
    assert main.DEV is False
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.post("/dev/trace").status_code == 404
    paths = {getattr(r, "path", None) for r in main.app.routes}
    assert "/dev/trace" not in paths and "/docs" not in paths and "/openapi.json" not in paths


def test_default_app_env_is_prod(monkeypatch):
    from placewise import config

    monkeypatch.delenv("APP_ENV", raising=False)
    config.get_settings.cache_clear()
    try:
        assert config.get_settings().app_env == "prod"
    finally:
        config.get_settings.cache_clear()


def test_invalid_app_env_is_rejected(monkeypatch):
    import pydantic
    import pytest

    from placewise import config

    monkeypatch.setenv("APP_ENV", "staging")
    config.get_settings.cache_clear()
    try:
        with pytest.raises(pydantic.ValidationError):
            config.get_settings()
    finally:
        config.get_settings.cache_clear()


def test_prod_health_ok_reduces_details(load_app, mock_checks):
    main, client = load_app("prod")
    mock_checks(main)
    r = client.get("/api/health")
    assert r.status_code == 200
    checks = r.json()["checks"]
    assert checks == {k: {"ok": True, "detail": "connected"} for k in ("api", "db", "langsmith")}
    assert "pgvector" not in r.text and "placewise" not in r.text and "v0." not in r.text


def test_prod_health_down_reduces_details(load_app, mock_checks):
    main, client = load_app("prod")
    mock_checks(main, db=DB_DOWN, langsmith=LS_DOWN)
    r = client.get("/api/health")
    assert r.status_code == 503
    body = r.json()
    assert body["ok"] is False
    assert body["checks"]["db"] == {"ok": False, "detail": "unavailable"}
    assert body["checks"]["langsmith"] == {"ok": False, "detail": "unavailable"}
    assert "OperationalError" not in r.text and "ConnectError" not in r.text
