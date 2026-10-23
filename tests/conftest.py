"""Shared fixtures for the API unit tests.

These tests run inside the api container but must never touch the real database or
LangSmith. The env is overridden BEFORE placewise.main is imported (settings and DEV
are computed at import time), and the health checks are mocked per test.
"""
import importlib
import os

import pytest

# Safe, synthetic env. Set before any placewise import.
_TEST_ENV = {
    "APP_ENV": "dev",
    "DATABASE_URL": "postgresql://test:test@127.0.0.1:1/test",  # unreachable on purpose
    "APP_SECRET_KEY": "test-secret-not-real",
    "LANGSMITH_TRACING": "false",
    "LANGSMITH_API_KEY": "lsv2-test-fake-key",
}
os.environ.update(_TEST_ENV)

from fastapi.testclient import TestClient  # noqa: E402

from placewise import config, health  # noqa: E402


def _reload_main():
    config.get_settings.cache_clear()
    import placewise.main as main

    return importlib.reload(main)


@pytest.fixture(autouse=True)
def _reset_langsmith_cache():
    health._langsmith_cache = None
    yield
    health._langsmith_cache = None


@pytest.fixture
def load_app(monkeypatch):
    """Return a loader that (re)imports placewise.main under a given APP_ENV.

    TestClient is used WITHOUT a `with` block, so the lifespan (which opens the real
    DB pool) never runs.
    """

    def _load(app_env: str = "dev"):
        monkeypatch.setenv("APP_ENV", app_env)
        main = _reload_main()
        return main, TestClient(main.app)

    yield _load
    # Restore the dev module for the next test.
    os.environ["APP_ENV"] = "dev"
    _reload_main()


OK_DB = {"ok": True, "detail": "connected, pgvector 0.8.1"}
OK_LS = {"ok": True, "detail": "authenticated, tracing on, project 'placewise'"}


@pytest.fixture
def mock_checks(monkeypatch):
    """Patch the checks that main.py imported, with async stubs returning given dicts."""

    def _set(main, db=OK_DB, langsmith=OK_LS):
        async def fake_db():
            return db

        async def fake_ls():
            if isinstance(langsmith, BaseException):
                raise langsmith
            return langsmith

        monkeypatch.setattr(main, "check_db", fake_db)
        monkeypatch.setattr(main, "check_langsmith", fake_ls)

    return _set
