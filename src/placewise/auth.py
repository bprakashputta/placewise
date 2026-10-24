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

import asyncio
import hmac
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
    """The client's address as seen by OUR proxy. The rightmost X-Forwarded-For entry is the one Next.js
    appended; earlier entries are client-controlled and could be spoofed to dodge the rate limit.
    Behind the Cloudflare tunnel, CF-Connecting-IP is set by Cloudflare itself. Through our Worker,
    x-placewise-client-ip is trusted only together with the Worker's shared secret."""
    secret = get_settings().origin_shared_secret
    if secret and secret.get_secret_value():
        sent = request.headers.get("x-placewise-origin", "")
        ip = request.headers.get("x-placewise-client-ip", "").strip()
        if ip and hmac.compare_digest(sent.encode(), secret.get_secret_value().encode()):
            return ip[:64]
    cf = request.headers.get("cf-connecting-ip")
    if cf and get_settings().trust_cloudflare_ip:   # only behind our Cloudflare tunnel; otherwise spoofable
        return cf.strip()
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def _rate_limited(*keys: str) -> bool:
    """Limited if ANY key (client IP, or the username being tried) has too many recent failures."""
    now = time.monotonic()
    limited = False
    for key in keys:
        q = _failures.get(key)
        if not q:
            continue
        while q and now - q[0] > LOGIN_WINDOW_S:
            q.popleft()
        if not q:
            _failures.pop(key, None)   # evict, so spoofed or one-off keys don't pile up
        elif len(q) >= LOGIN_LIMIT:
            limited = True
    return limited


class LoginBody(BaseModel):
    username: str
    password: str


def _public(user: dict) -> dict:
    return {"username": user["username"], "display_name": user["display_name"], "role": user["role"]}


@router.post("/login")
async def login(body: LoginBody, request: Request, response: Response) -> dict:
    ip = _client_ip(request)
    uname = body.username.strip().lower()[:100]
    ukey = f"user:{uname}"
    if _rate_limited(f"ip:{ip}", ukey):
        raise HTTPException(429, "Too many attempts, wait a minute")
    async with pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute("SELECT id, username, display_name, role, password_hash FROM users "
                          "WHERE username = %s AND is_active", (uname,))
        user = await cur.fetchone()
    # Argon2 is deliberately slow: verify in a thread (not on the event loop, not holding a DB connection)
    ok = await asyncio.to_thread(verify_password, body.password, user["password_hash"] if user else _DUMMY_HASH)
    if not (user and ok):
        _failures[f"ip:{ip}"].append(time.monotonic())
        _failures[ukey].append(time.monotonic())
        raise HTTPException(401, "Wrong username or password")
    async with pool().connection() as conn:
        await conn.execute("UPDATE users SET last_login_at = now() WHERE id = %s", (user["id"],))
    _failures.pop(f"ip:{ip}", None)
    _failures.pop(ukey, None)
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
