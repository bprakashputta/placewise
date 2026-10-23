"""Portal authentication: username + password (Argon2id), signed session cookie, two roles.

- Session = a signed, timestamped token in an httpOnly cookie (itsdangerous, keyed by APP_SECRET_KEY).
  Tampering breaks the signature; tokens expire after SESSION_HOURS. The user row is re-checked on
  every request, so disabling a user takes effect immediately.
- Roles: admin (everything) and recruiter (everything except admin-only routes).
- Login is rate limited per client IP to slow down password guessing.
- Demo users are created on startup from PLACEWISE_DEMO_*_PASSWORD env vars (if set), so the
  passwords live only in .env.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from psycopg.rows import dict_row
from pydantic import BaseModel

from .config import get_settings
from .db import pool

COOKIE = "pw_session"
SESSION_HOURS = 12
LOGIN_LIMIT, LOGIN_WINDOW_S = 5, 60          # max failed attempts per IP per window
_hasher = PasswordHasher()
_failures: dict[str, deque] = defaultdict(deque)
# A real hash of a random string, so unknown usernames take as long as wrong passwords (no user enumeration)
_DUMMY_HASH = _hasher.hash(os.urandom(16).hex())

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().app_secret_key.get_secret_value(), salt="placewise-session")


def hash_password(pw: str) -> str:
    return _hasher.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, pw)
    except (VerificationError, InvalidHashError):
        return False


async def _load_user(user_id: int) -> dict | None:
    async with pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute("SELECT id, username, display_name, role FROM users WHERE id = %s AND is_active",
                          (user_id,))
        return await cur.fetchone()


async def current_user(request: Request) -> dict:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Not signed in")
    try:
        data = _serializer().loads(token, max_age=SESSION_HOURS * 3600)
    except SignatureExpired:
        raise HTTPException(401, "Session expired, please sign in again")
    except BadSignature:
        raise HTTPException(401, "Not signed in")
    user = await _load_user(int(data["uid"]))
    if user is None:
        raise HTTPException(401, "Account not found or disabled")
    return user


async def require_admin(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(403, "Admins only")
    return user


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


def _rate_limited(ip: str) -> bool:
    q, now = _failures[ip], time.monotonic()
    while q and now - q[0] > LOGIN_WINDOW_S:
        q.popleft()
    return len(q) >= LOGIN_LIMIT


class LoginBody(BaseModel):
    username: str
    password: str


def _public(user: dict) -> dict:
    return {"username": user["username"], "display_name": user["display_name"], "role": user["role"]}


@router.post("/login")
async def login(body: LoginBody, request: Request, response: Response) -> dict:
    ip = _client_ip(request)
    if _rate_limited(ip):
        raise HTTPException(429, "Too many attempts, wait a minute")
    async with pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute("SELECT id, username, display_name, role, password_hash FROM users "
                          "WHERE username = %s AND is_active", (body.username.strip().lower(),))
        user = await cur.fetchone()
        ok = verify_password(body.password, user["password_hash"] if user else _DUMMY_HASH)
        if not (user and ok):
            _failures[ip].append(time.monotonic())
            raise HTTPException(401, "Wrong username or password")
        await conn.execute("UPDATE users SET last_login_at = now() WHERE id = %s", (user["id"],))
    _failures.pop(ip, None)
    token = _serializer().dumps({"uid": user["id"], "role": user["role"]})
    response.set_cookie(COOKIE, token, max_age=SESSION_HOURS * 3600, httponly=True, samesite="lax",
                        secure=get_settings().cookie_secure, path="/")
    return {"user": _public(user)}


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(current_user)) -> dict:
    return {"user": _public(user)}


async def ensure_demo_users() -> list[str]:
    """Create or refresh the demo accounts from env vars (no-op if the vars aren't set)."""
    made = []
    demo = [("admin", "Demo Admin", "admin", os.environ.get("PLACEWISE_DEMO_ADMIN_PASSWORD")),
            ("recruiter", "Demo Recruiter", "recruiter", os.environ.get("PLACEWISE_DEMO_RECRUITER_PASSWORD"))]
    async with pool().connection() as conn:
        for username, name, role, pw in demo:
            if not pw:
                continue
            cur = await conn.execute("SELECT password_hash FROM users WHERE username = %s", (username,))
            row = await cur.fetchone()
            if row and verify_password(pw, row[0]):
                continue
            await conn.execute(
                """INSERT INTO users (username, display_name, role, password_hash) VALUES (%s,%s,%s,%s)
                   ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash,
                       role = EXCLUDED.role, display_name = EXCLUDED.display_name, is_active = TRUE""",
                (username, name, role, hash_password(pw)))
            made.append(username)
    return made
