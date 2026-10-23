"""Conversational Ask (ADR 018): routing shortcuts, code-written replies, follow-up scoping,
job-order plans and the conversations API (validation, ownership, spend cap, nothing saved on failure)."""
import asyncio
from datetime import datetime

import pytest

from placewise import auth
from placewise.ingest.spend import SpendCapReached
from placewise.rag import converse
from placewise.rag.retrieve import Filters, _where

RECRUITER = {"id": 2, "username": "recruiter", "display_name": "Demo Recruiter", "role": "recruiter"}


# ---------- free keyword routing ----------

@pytest.mark.parametrize("msg,intent,flavor", [
    ("hi", "greeting", "hello"), ("Hey!", "greeting", "hello"), ("hello there", "greeting", "hello"),
    ("Good morning", "greeting", "hello"), ("heyyy", "greeting", "hello"), ("thanks!", "greeting", "thanks"),
    ("thank you so much", "greeting", "thanks"), ("ok", "greeting", "thanks"), ("bye", "greeting", "bye"),
    ("help", "help", ""), ("what can you do?", "help", ""),
])
def test_quick_route_obvious_one_liners(msg, intent, flavor):
    assert converse.quick_route(msg) == (intent, flavor)


REAL_REQUESTS = [
    "hi, any Texas PEs in Houston?", "PMP", "hey can you find structural engineers", "Texas PEs in DFW",
    "which of them have PMP?", "who fits JO-03?", "hello " * 10,
]


@pytest.mark.parametrize("msg", ["sssssss", "asdf", "???", "...", "qwertyu"])
def test_quick_route_catches_gibberish(msg):
    assert converse.quick_route(msg) == ("unclear", "")


def test_model_small_talk_reply_is_used_and_never_searches(monkeypatch):
    async def go():
        async def boom(*a, **k):
            raise AssertionError("must not search")
        monkeypatch.setattr(converse, "run_rag", boom)
        monkeypatch.setattr(converse, "route", _route(converse.Route(intent="greeting", reply="Doing well, thanks!")))
        out = await converse.respond("how are you doing", [], RECRUITER, None)
        assert out["kind"] == "greeting" and out["content"] == "Doing well, thanks!"
        monkeypatch.setattr(converse, "route", _route(converse.Route(intent="unclear")))
        out = await converse.respond("zzzx", [], RECRUITER, None)
        assert out["kind"] == "off_topic" and "didn't catch" in out["content"] or "not sure" in out["content"]
    asyncio.run(go())


@pytest.mark.parametrize("msg", REAL_REQUESTS)
def test_quick_route_leaves_real_requests_to_the_model(msg):
    assert converse.quick_route(msg) is None


# ---------- replies written by code ----------

CTX = {"to_review": 2, "no_run": 1, "no_run_id": 16, "new_today": 3, "attention": 0}


def test_first_greeting_of_the_day_has_context_and_suggestions():
    text, sugg = converse.greeting_reply("hello", "Demo", True, CTX, datetime(2026, 10, 23, 9), None)
    assert text.startswith("Good morning, Demo!")
    assert "2 job orders have a shortlist" in text and "1 open job order has" in text and "3 new resumes" in text
    assert "attention" not in text                      # zero counts are left out
    assert sugg[0] == "Who fits JO-16?" and len(sugg) <= 3


def test_later_greetings_are_short():
    text, _ = converse.greeting_reply("hello", "Demo", False, None, datetime(2026, 10, 23, 15), None)
    assert "Demo" in text and len(text) < 90 and "job orders" not in text      # short, varied, no status dump
    assert converse.greeting_reply("thanks", "Demo", True, CTX, datetime.now(), None)[0].startswith("You're welcome")


def test_greeting_in_a_job_order_chat_mentions_the_role():
    jo = {"id": 3, "spec": {"title": "Drainage Engineer"}}
    text, sugg = converse.greeting_reply("hello", "Demo", False, None, datetime(2026, 10, 23, 19), jo)
    assert "Drainage Engineer" in text and "JO-03" in text and sugg == ["Who are the top candidates for this role?"]


# ---------- follow-ups and job orders ----------

def test_where_restricts_to_previous_candidates():
    sql, args = _where(Filters(metro="DFW"), [5, 9])
    assert "c.person_id = ANY(%s)" in sql and args[0] == [5, 9]
    sql, args = _where(Filters())
    assert "person_id" not in sql and args == []


SPEC = {"title": "Drainage Engineer", "metro": "Houston", "discipline": "civil", "subdiscipline": "drainage",
        "requirements": [
            {"text": "Texas PE license", "kind": "license", "priority": "must", "key": "PE", "state": "TX"},
            {"text": "6+ years", "kind": "years", "priority": "must", "value": "6"},
            {"text": "HEC-RAS", "kind": "software", "priority": "must", "key": "HEC-RAS"},
            {"text": "Civil 3D", "kind": "software", "priority": "nice"}]}


def test_job_order_plan_uses_structured_requirements():
    plan = converse.job_order_plan({"id": 3, "spec": SPEC})
    f = plan["filters"]
    assert f["license_codes"] == ["PE:TX"] and f["metro"] == "Houston" and f["discipline"] == "civil"
    assert f["min_years"] == 5.0                        # one year short can still be 'partial', as in matching
    assert "HEC-RAS" in plan["search_query"] and "Civil 3D" in plan["search_query"]


async def _fake_rag(captured, candidates):
    async def run(question, plan_override=None, person_ids=None, run_name="ask"):
        captured.update(question=question, plan_override=plan_override, person_ids=person_ids, run_name=run_name)
        return {"answer": "ok", "citations": [{"person_id": p, "candidate_name": f"C{p}"} for p in candidates],
                "candidates": [{"person_id": p, "full_name": f"C{p}"} for p in candidates], "plan": {},
                "cost_usd": 0.03}
    return run


def test_follow_up_searches_only_the_cited_candidates(monkeypatch):
    asyncio.run(_test_follow_up_searches_only_the_cited_candidates(monkeypatch))


async def _test_follow_up_searches_only_the_cited_candidates(monkeypatch):
    captured = {}
    monkeypatch.setattr(converse, "route", _route(converse.Route(
        intent="follow_up", scope="previous_candidates", standalone_question="Which of the candidates from the "
        "previous answer have PMP?")))
    monkeypatch.setattr(converse, "run_rag", await _fake_rag(captured, [7]))
    history = [{"role": "user", "kind": "user", "content": "PEs in DFW"},
               {"role": "assistant", "kind": "search", "content": "...", "person_ids": [7, 8, 9], "response": {}}]
    out = await converse.respond("which of them have PMP?", history, RECRUITER, None)
    assert captured["person_ids"] == [7, 8, 9] and out["kind"] == "follow_up" and out["person_ids"] == [7]


def test_follow_up_with_no_match_offers_whole_pool(monkeypatch):
    asyncio.run(_test_follow_up_with_no_match_offers_whole_pool(monkeypatch))


async def _test_follow_up_with_no_match_offers_whole_pool(monkeypatch):
    monkeypatch.setattr(converse, "route", _route(converse.Route(
        intent="follow_up", scope="previous_candidates",
        standalone_question="Which of the candidates from the previous answer have 20+ years?")))
    monkeypatch.setattr(converse, "run_rag", await _fake_rag({}, []))
    history = [{"role": "assistant", "kind": "search", "content": "...", "person_ids": [7, 8], "response": {}}]
    out = await converse.respond("any with 20+ years?", history, RECRUITER, None)
    assert out["content"].startswith("None of the 2 candidates from the previous answer")
    assert out["suggestions"] == ["Search everyone: Which have 20+ years?"]


def test_off_topic_and_help_never_search(monkeypatch):
    asyncio.run(_test_off_topic_and_help_never_search(monkeypatch))


async def _test_off_topic_and_help_never_search(monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("must not search")
    monkeypatch.setattr(converse, "run_rag", boom)
    for intent in ("off_topic", "help"):
        monkeypatch.setattr(converse, "route", _route(converse.Route(intent=intent)))
        out = await converse.respond("whatever", [], RECRUITER, None)
        assert out["kind"] == intent and out["response"] is None


def _route(r):
    async def fake(message, history, jo):
        return r, {"flavor": "hello", "cost_usd": 0.0}
    return fake


# ---------- API ----------

@pytest.fixture
def client(load_app):
    main, c = load_app("dev")
    main.app.dependency_overrides[auth.current_user] = lambda: RECRUITER
    yield main, c
    main.app.dependency_overrides.clear()


def test_message_validation_never_reaches_the_model(client, monkeypatch):
    from placewise import conversations_api
    main, c = client

    async def never(*a, **k):
        raise AssertionError("invalid bodies must not be processed")
    monkeypatch.setattr(conversations_api, "respond", never)
    for bad in ({}, {"content": ""}, {"content": "   "}, {"content": "a" * 2001}):
        assert c.post("/api/conversations/1/messages", json=bad).status_code == 422, bad


def test_other_users_conversation_is_404_and_spend_cap_saves_nothing(client, monkeypatch):
    from placewise import conversations_api
    main, c = client
    state = {"conv": None, "inserts": 0}

    async def get_conv(conn, conv_id, user_id):
        from fastapi import HTTPException
        if state["conv"] is None:
            raise HTTPException(404, "conversation not found")
        return state["conv"]

    async def messages(conn, conv_id):
        return []

    async def capped(*a, **k):
        raise SpendCapReached("cap")

    class Conn:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        def transaction(self):
            state["inserts"] += 1
            return self

    class Pool:
        def connection(self): return Conn()

    monkeypatch.setattr(conversations_api, "_get_conv", get_conv)
    monkeypatch.setattr(conversations_api, "_messages", messages)
    monkeypatch.setattr(conversations_api, "pool", lambda: Pool())
    monkeypatch.setattr(conversations_api, "respond", capped)
    assert c.post("/api/conversations/5/messages", json={"content": "hi"}).status_code == 404
    assert c.get("/api/conversations/5").status_code == 404
    state["conv"] = {"id": 5, "job_order_id": None}
    assert c.post("/api/conversations/5/messages", json={"content": "PEs in DFW"}).status_code == 429
    assert state["inserts"] == 0                       # nothing saved when the turn fails


def test_license_without_state_matches_any_state():
    sql, args = _where(Filters(license_codes=["RA", "PE:TX", "TX_RID"]))
    assert "lc LIKE %s" in sql and args[:2] == ["RA", "RA:%"]
    assert "PE:TX" in args and "TX\\_RID:%" in args       # underscore escaped for LIKE
