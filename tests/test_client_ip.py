"""Login rate-limit key: which client IP the api trusts (PR #5 review)."""
import secrets

import pytest
from starlette.requests import Request

from placewise import auth, config


def _req(headers: dict, client=("10.0.0.9", 1234)) -> Request:
    return Request({"type": "http", "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
                    "client": client})


@pytest.fixture
def settings(monkeypatch):
    def apply(**env):
        for k in ("ORIGIN_SHARED_SECRET", "TRUST_CLOUDFLARE_IP"):
            monkeypatch.delenv(k, raising=False)
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        config.get_settings.cache_clear()
    yield apply
    config.get_settings.cache_clear()


def test_worker_ip_trusted_with_the_secret(settings):
    s = secrets.token_hex(16)
    settings(ORIGIN_SHARED_SECRET=s, TRUST_CLOUDFLARE_IP="true")
    r = _req({"x-placewise-origin": s, "x-placewise-client-ip": "203.0.113.7", "cf-connecting-ip": "2a06:98c0::1"})
    assert auth._client_ip(r) == "203.0.113.7"


def test_worker_ip_ignored_with_a_wrong_secret(settings):
    settings(ORIGIN_SHARED_SECRET=secrets.token_hex(16), TRUST_CLOUDFLARE_IP="true")
    r = _req({"x-placewise-origin": "guess", "x-placewise-client-ip": "203.0.113.7", "cf-connecting-ip": "198.51.100.4"})
    assert auth._client_ip(r) == "198.51.100.4"


def test_worker_ip_ignored_when_no_secret_is_configured(settings):
    settings()   # local development: no secret, no Cloudflare
    r = _req({"x-placewise-origin": "", "x-placewise-client-ip": "203.0.113.7", "x-forwarded-for": "1.2.3.4, 172.18.0.5"})
    assert auth._client_ip(r) == "172.18.0.5"


def test_secret_without_client_ip_falls_back(settings):
    s = secrets.token_hex(16)
    settings(ORIGIN_SHARED_SECRET=s)
    assert auth._client_ip(_req({"x-placewise-origin": s})) == "10.0.0.9"
