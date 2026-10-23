"""Unit tests for placewise.health: check_db, _check_langsmith_sync and the cache."""
import asyncio
import types

import pytest

from placewise import health


# ---------- check_db (pool/connection mocked) ----------

class _Cur:
    def __init__(self, row):
        self._row = row

    async def fetchone(self):
        return self._row


class _Conn:
    def __init__(self, row):
        self.row = row
        self.sql = None

    async def execute(self, sql):
        self.sql = sql
        return _Cur(self.row)


class _ConnCM:
    def __init__(self, conn=None, exc=None):
        self.conn, self.exc = conn, exc

    async def __aenter__(self):
        if self.exc:
            raise self.exc
        return self.conn

    async def __aexit__(self, *a):
        return False


class _Pool:
    def __init__(self, conn=None, exc=None):
        self.conn, self.exc = conn, exc
        self.timeout = None

    def connection(self, timeout=None):
        self.timeout = timeout
        return _ConnCM(self.conn, self.exc)


def _run(coro):
    return asyncio.run(coro)


def test_check_db_ok_with_pgvector(monkeypatch):
    conn = _Conn(("0.8.1",))
    p = _Pool(conn)
    monkeypatch.setattr(health, "pool", lambda: p)
    assert _run(health.check_db()) == {"ok": True, "detail": "connected, pgvector 0.8.1"}
    assert "pg_extension" in conn.sql and "vector" in conn.sql
    assert p.timeout == 3  # bounded wait for a pool connection


def test_check_db_reports_missing_pgvector(monkeypatch):
    monkeypatch.setattr(health, "pool", lambda: _Pool(_Conn(None)))
    r = _run(health.check_db())
    assert r["ok"] is False
    assert "pgvector extension is not installed" in r["detail"]


def test_check_db_connection_error_hides_details(monkeypatch):
    secret = "postgresql://placewise:supersecret@db:5432/placewise"
    monkeypatch.setattr(health, "pool", lambda: _Pool(exc=ConnectionError(secret)))
    r = _run(health.check_db())
    assert r == {"ok": False, "detail": "cannot connect (ConnectionError)"}
    assert "supersecret" not in r["detail"]


def test_check_db_pool_not_open(monkeypatch):
    def not_open():
        raise RuntimeError("Database pool is not open")

    monkeypatch.setattr(health, "pool", not_open)
    assert _run(health.check_db()) == {"ok": False, "detail": "cannot connect (RuntimeError)"}


# ---------- _check_langsmith_sync (Client mocked) ----------

class _FakeClient:
    def __init__(self, *a, fail=None, **kw):
        self.kw = kw
        self.fail = fail

    def list_projects(self, limit=1):
        if self.fail:
            raise self.fail
        return iter([object()])


def test_langsmith_sync_ok(monkeypatch):
    seen = {}

    def make(**kw):
        seen.update(kw)
        return _FakeClient(**kw)

    monkeypatch.setattr(health, "Client", make)
    r = health._check_langsmith_sync()
    assert r["ok"] is True and "authenticated" in r["detail"]
    assert seen["api_key"] == "lsv2-test-fake-key"  # from the test env, not a real key


def test_langsmith_sync_missing_key(monkeypatch):
    from placewise import config

    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    config.get_settings.cache_clear()
    monkeypatch.setattr(health, "Client", lambda **kw: pytest.fail("must not build a client"))
    try:
        assert health._check_langsmith_sync() == {"ok": False, "detail": "LANGSMITH_API_KEY not set"}
    finally:
        config.get_settings.cache_clear()


def test_langsmith_sync_error_hides_key(monkeypatch):
    monkeypatch.setattr(
        health, "Client", lambda **kw: _FakeClient(fail=PermissionError("bad key lsv2-test-fake-key"))
    )
    r = health._check_langsmith_sync()
    assert r == {"ok": False, "detail": "cannot reach LangSmith (PermissionError)"}


# ---------- check_langsmith cache (time.monotonic patched) ----------

class _Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def clock(monkeypatch):
    c = _Clock()
    # Patch only health.py view of time: patching time.monotonic globally would
    # also freeze the asyncio event loop clock and break wait_for.
    monkeypatch.setattr(health, "time", types.SimpleNamespace(monotonic=c))
    return c


@pytest.fixture
def sync_results(monkeypatch):
    """Queue of results returned by successive _check_langsmith_sync calls."""
    calls = []
    queue = []

    def fake():
        calls.append(1)
        return queue.pop(0)

    monkeypatch.setattr(health, "_check_langsmith_sync", fake)
    return queue, calls


FAIL = {"ok": False, "detail": "cannot reach LangSmith (ConnectError)"}
OK = {"ok": True, "detail": "authenticated, tracing on, project 'placewise'"}


def test_failure_is_cached_for_15s(clock, sync_results):
    queue, calls = sync_results
    queue += [FAIL, OK]
    assert _run(health.check_langsmith()) == FAIL
    clock.t += 14.9
    assert _run(health.check_langsmith()) == FAIL
    assert len(calls) == 1  # served from cache
    clock.t += 0.2  # 15.1s after the first check
    assert _run(health.check_langsmith()) == OK
    assert len(calls) == 2


def test_success_is_cached_for_60s(clock, sync_results):
    queue, calls = sync_results
    queue += [OK, FAIL]
    assert _run(health.check_langsmith()) == OK
    clock.t += 59.9
    assert _run(health.check_langsmith()) == OK
    assert len(calls) == 1
    clock.t += 0.2
    assert _run(health.check_langsmith()) == FAIL
    assert len(calls) == 2


def test_timeout_is_cached_as_failure_for_15s(clock, monkeypatch):
    import time as _time

    calls = []

    def slow():
        calls.append(1)
        _time.sleep(0.3)
        return OK

    monkeypatch.setattr(health, "_check_langsmith_sync", slow)
    real_wait_for = asyncio.wait_for
    monkeypatch.setattr(health.asyncio, "wait_for", lambda aw, timeout: real_wait_for(aw, 0.05))
    assert _run(health.check_langsmith()) == {"ok": False, "detail": "timed out"}
    clock.t += 10
    assert _run(health.check_langsmith()) == {"ok": False, "detail": "timed out"}
    assert len(calls) == 1  # no new thread started during the outage window
    assert health._langsmith_cache[1] == 15


def test_real_timeout_constant_is_10s(monkeypatch, clock):
    """The production timeout passed to wait_for is 10 seconds."""
    seen = {}

    async def fake_wait_for(aw, timeout):
        seen["timeout"] = timeout
        aw.close()
        return OK

    monkeypatch.setattr(health.asyncio, "wait_for", fake_wait_for)
    _run(health.check_langsmith())
    assert seen["timeout"] == 10
