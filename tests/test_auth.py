"""Block 3: authentication. No database: users and the pool are faked."""
import time

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from placewise import auth


class FakeCursor:
    def __init__(self, db):
        self.db, self.row = db, None

    async def execute(self, sql, params=None):
        if sql.lstrip().upper().startswith("SELECT"):
            key = params[0]
            self.row = self.db["by_name"].get(key) if isinstance(key, str) else self.db["by_id"].get(key)
        return self

    async def fetchone(self):
        return self.row


class FakeConn:
    def __init__(self, db):
        self.db = db

    def cursor(self, row_factory=None):
        return FakeCursor(self.db)

    async def execute(self, sql, params=None):
        return FakeCursor(self.db)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class FakePool:
    def __init__(self, db):
        self.db = db

    def connection(self):
        return FakeConn(self.db)


@pytest.fixture
def app(monkeypatch):
    admin = {"id": 1, "username": "admin", "display_name": "Demo Admin", "role": "admin",
             "password_hash": auth.hash_password("correct-horse")}
    rec = {"id": 2, "username": "recruiter", "display_name": "Demo Recruiter", "role": "recruiter",
           "password_hash": auth.hash_password("battery-staple")}
    db = {"by_name": {"admin": admin, "recruiter": rec}, "by_id": {1: admin, 2: rec}}
    monkeypatch.setattr(auth, "pool", lambda: FakePool(db))
    auth._failures.clear()
    a = FastAPI()
    a.include_router(auth.router)

    @a.get("/api/private")
    async def private(user=Depends(auth.current_user)):
        return {"who": user["username"]}

    @a.get("/api/admin-only")
    async def admin_only(user=Depends(auth.require_admin)):
        return {"ok": True}

    return TestClient(a)


def login(c, u, p):
    return c.post("/api/auth/login", json={"username": u, "password": p})


def test_password_hash_roundtrip():
    import secrets
    pw = secrets.token_urlsafe(12)   # generated per run: no fixed password string in the repo
    h = auth.hash_password(pw)
    assert h.startswith("$argon2") and auth.verify_password(pw, h)
    assert not auth.verify_password("wrong", h)
    assert not auth.verify_password("x", "not-a-hash")


def test_login_sets_httponly_cookie_and_me_works(app):
    r = login(app, "admin", "correct-horse")
    assert r.status_code == 200 and r.json()["user"] == {"username": "admin", "display_name": "Demo Admin",
                                                         "role": "admin"}
    cookie = r.headers["set-cookie"]
    assert "pw_session=" in cookie and "HttpOnly" in cookie and "samesite=lax" in cookie.lower()
    assert "password" not in r.text
    assert app.get("/api/auth/me").json()["user"]["role"] == "admin"


def test_username_is_case_insensitive(app):
    assert login(app, "  Admin ", "correct-horse").status_code == 200


def test_wrong_password_and_unknown_user_are_both_401(app):
    assert login(app, "admin", "nope").status_code == 401
    assert login(app, "ghost", "nope").status_code == 401


def test_protected_route_requires_session(app):
    assert app.get("/api/private").status_code == 401
    login(app, "recruiter", "battery-staple")
    assert app.get("/api/private").json() == {"who": "recruiter"}


def test_recruiter_cannot_use_admin_routes(app):
    login(app, "recruiter", "battery-staple")
    assert app.get("/api/admin-only").status_code == 403
    login(app, "admin", "correct-horse")
    assert app.get("/api/admin-only").status_code == 200


def test_tampered_or_forged_cookie_rejected(app):
    login(app, "recruiter", "battery-staple")
    good = app.cookies.get("pw_session")
    # Swap in a payload claiming to be user 1 (admin) while keeping the recruiter's signature.
    # (Flipping the signature's last base64 char is NOT a reliable tamper: it can carry unused bits.)
    import base64
    import json
    payload, *rest = good.split(".")
    evil = base64.urlsafe_b64encode(json.dumps({"uid": 1, "role": "admin"}).encode()).decode().rstrip("=")
    app.cookies.clear()  # otherwise the client keeps (and sends) the original cookie too
    app.cookies.set("pw_session", ".".join([evil, *rest]))
    assert app.get("/api/private").status_code == 401
    # A token signed with a different key (attacker forging an admin session)
    from itsdangerous import URLSafeTimedSerializer
    forged = URLSafeTimedSerializer("attacker-key", salt="placewise-session").dumps({"uid": 1, "role": "admin"})
    app.cookies.clear()
    app.cookies.set("pw_session", forged)
    assert app.get("/api/admin-only").status_code == 401


def test_expired_session_rejected(app, monkeypatch):
    login(app, "admin", "correct-horse")
    monkeypatch.setattr(auth, "SESSION_HOURS", 0)
    time.sleep(1.1)
    r = app.get("/api/private")
    assert r.status_code == 401 and "expired" in r.json()["detail"].lower()


def test_rate_limit_after_five_failures(app):
    codes = [login(app, "admin", "wrong").status_code for _ in range(6)]
    assert codes == [401] * 5 + [429]
    assert login(app, "admin", "correct-horse").status_code == 429  # still locked inside the window


def test_logout_clears_session(app):
    login(app, "admin", "correct-horse")
    app.post("/api/auth/logout")
    assert app.get("/api/auth/me").status_code == 401
