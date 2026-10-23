"""Saved Ask conversations (ADR 018). Every route requires a signed-in user; each user sees only
their own conversations (another user's id returns 404, not 403, so ids can't be probed)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel, Field, field_validator

from .auth import current_user
from .db import pool
from .ingest.spend import SpendCapReached
from .rag.converse import intro_message, load_job_order, respond

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

_CONV_SQL = """
    SELECT c.id, c.title, c.job_order_id, j.title AS job_order_title, c.created_at, c.last_message_at,
           (c.last_message_at > now() - interval '24 hours' AND (j.id IS NULL OR j.status = 'open')) AS active,
           (SELECT count(*) FROM conversation_messages m WHERE m.conversation_id = c.id) AS message_count
    FROM conversations c LEFT JOIN job_orders j ON j.id = c.job_order_id
"""
_MSG_COLS = "id, role, kind, content, response, suggestions, person_ids, created_at"


class NewConversation(BaseModel):
    job_order_id: int | None = None


class NewMessage(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message is empty")
        return v.strip()


def _public(m: dict) -> dict:
    return {k: m[k] for k in ("id", "role", "kind", "content", "response", "suggestions", "created_at")}


async def _get_conv(conn, conv_id: int, user_id: int) -> dict:
    cur = conn.cursor(row_factory=dict_row)
    await cur.execute(_CONV_SQL + " WHERE c.id = %s AND c.user_id = %s", (conv_id, user_id))
    conv = await cur.fetchone()
    if not conv:
        raise HTTPException(404, "conversation not found")
    return conv


async def _messages(conn, conv_id: int) -> list[dict]:
    cur = conn.cursor(row_factory=dict_row)
    await cur.execute(f"SELECT {_MSG_COLS} FROM conversation_messages WHERE conversation_id = %s ORDER BY id",
                      (conv_id,))
    return await cur.fetchall()


@router.get("")
async def list_conversations(user: dict = Depends(current_user)) -> list[dict]:
    async with pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(_CONV_SQL + " WHERE c.user_id = %s ORDER BY c.last_message_at DESC LIMIT 50",
                          (user["id"],))
        return await cur.fetchall()


@router.post("")
async def create_conversation(body: NewConversation, user: dict = Depends(current_user)) -> dict:
    jo = await load_job_order(body.job_order_id) if body.job_order_id else None
    if body.job_order_id and not jo:
        raise HTTPException(404, "job order not found")
    async with pool().connection() as conn:
        async with conn.transaction():
            cur = await conn.execute(
                "INSERT INTO conversations (user_id, title, job_order_id) VALUES (%s, %s, %s) RETURNING id",
                (user["id"], jo["title"] if jo else "New chat", jo["id"] if jo else None))
            conv_id = (await cur.fetchone())[0]
            if jo:
                text, sugg = intro_message(jo)
                await conn.execute("INSERT INTO conversation_messages (conversation_id, role, kind, content, "
                                   "suggestions) VALUES (%s, 'assistant', 'intro', %s, %s)", (conv_id, text, sugg))
        conv = await _get_conv(conn, conv_id, user["id"])
        return {**conv, "messages": [_public(m) for m in await _messages(conn, conv_id)]}


@router.get("/{conv_id}")
async def get_conversation(conv_id: int, user: dict = Depends(current_user)) -> dict:
    async with pool().connection() as conn:
        conv = await _get_conv(conn, conv_id, user["id"])
        return {**conv, "messages": [_public(m) for m in await _messages(conn, conv_id)]}


@router.post("/{conv_id}/messages")
async def send_message(conv_id: int, body: NewMessage, user: dict = Depends(current_user)) -> dict:
    async with pool().connection() as conn:
        conv = await _get_conv(conn, conv_id, user["id"])
        history = await _messages(conn, conv_id)
    jo = await load_job_order(conv["job_order_id"])
    try:
        reply = await respond(body.content, history, user, jo)
    except SpendCapReached as e:
        raise HTTPException(429, str(e))
    # Save both messages only after a successful reply, so a failed turn leaves no half-saved state
    async with pool().connection() as conn:
        async with conn.transaction():
            cur = conn.cursor(row_factory=dict_row)
            await cur.execute(f"INSERT INTO conversation_messages (conversation_id, role, kind, content) "
                              f"VALUES (%s, 'user', 'user', %s) RETURNING {_MSG_COLS}", (conv_id, body.content))
            user_msg = await cur.fetchone()
            await cur.execute(
                f"""INSERT INTO conversation_messages (conversation_id, role, kind, content, response, suggestions,
                                                       person_ids, cost_usd)
                    VALUES (%s, 'assistant', %s, %s, %s, %s, %s, %s) RETURNING {_MSG_COLS}""",
                (conv_id, reply["kind"], reply["content"],
                 json.dumps(reply["response"], default=str) if reply["response"] is not None else None,
                 reply["suggestions"], reply["person_ids"], reply["cost_usd"]))
            bot_msg = await cur.fetchone()
            # Title: the first real question (greetings don't rename the chat)
            new_title = body.content[:60] + ("…" if len(body.content) > 60 else "")
            await conn.execute(
                """UPDATE conversations SET last_message_at = now(),
                       title = CASE WHEN title = 'New chat' AND job_order_id IS NULL AND %s THEN %s ELSE title END
                   WHERE id = %s""", (reply["kind"] in ("search", "follow_up", "job_order"), new_title, conv_id))
    return {"user_message": _public(user_msg), "assistant_message": _public(bot_msg)}
