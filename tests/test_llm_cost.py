"""Cache-aware Claude cost math (prompt caching) and the match prompt v3 layout."""
import pytest

from placewise import promptlib
from placewise.llm_cost import cached_system, usage_cost


def test_plain_call():
    c = usage_cost("claude-sonnet-5-5", {"input_tokens": 1000, "output_tokens": 500})
    assert c["usd"] == pytest.approx(1000 * 2.0 / 1e6 + 500 * 10.0 / 1e6)
    assert (c["cache_read"], c["cache_write"]) == (0, 0)


def test_cache_write_costs_125_percent():
    # shape reported by langchain-anthropic 1.7: input_tokens includes the cached part
    u = {"input_tokens": 2445, "output_tokens": 48,
         "input_token_details": {"cache_read": 0, "cache_creation": 0, "ephemeral_5m_input_tokens": 2361,
                                 "ephemeral_1h_input_tokens": 0}}
    c = usage_cost("claude-sonnet-5-5", u)
    assert c["usd"] == pytest.approx((84 * 2.0 + 2361 * 2.0 * 1.25 + 48 * 10.0) / 1e6)
    assert c["cache_write"] == 2361


def test_cache_read_costs_5_percent_on_sonnet_and_10_on_haiku():
    u = {"input_tokens": 2445, "output_tokens": 48, "input_token_details": {"cache_read": 2361}}
    assert usage_cost("claude-sonnet-5-5", u)["usd"] == pytest.approx((84 * 2.0 + 2361 * 0.10 + 48 * 10.0) / 1e6)
    assert usage_cost("claude-haiku-5-5", u)["usd"] == pytest.approx((84 * 0.10 + 2361 * 0.01 + 48 * 0.50) / 1e6)
    assert usage_cost("claude-sonnet-5-5", u)["cache_read"] == 2361


def test_older_payload_with_only_cache_creation():
    u = {"input_tokens": 1000, "output_tokens": 0, "input_token_details": {"cache_creation": 800}}
    assert usage_cost("claude-sonnet-5-5", u)["usd"] == pytest.approx((200 * 2.0 + 800 * 2.5) / 1e6)


def test_missing_usage_and_unknown_model_cost_zero():
    assert usage_cost("claude-sonnet-5-5", None)["usd"] == 0
    assert usage_cost("mystery", {"input_tokens": 10, "output_tokens": 10})["usd"] == 0


def test_cached_system_marks_cache_control():
    m = cached_system("instructions")
    assert m.content == [{"type": "text", "text": "instructions", "cache_control": {"type": "ephemeral"}}]


def test_match_prompt_v3_puts_the_job_in_the_cached_system_and_the_candidate_in_the_user():
    p = promptlib.load("match_score", 3)
    system = p["system"].format(title="Drainage PE", requirements="- [must] HEC-RAS", job_metro="DFW")
    user = p["user"].format(facts="licenses: PE:TX", profile="Hydraulic modeling in HEC-RAS")
    assert "Drainage PE" in system and "HEC-RAS" in system and "DFW" in system
    assert "Drainage PE" not in user and "PE:TX" in user and "Hydraulic modeling" in user
    assert "untrusted data" in system   # the injection warning stays in the instructions


# ---- LangChain response cache (llm_cache.py) ----
from langchain_core.load import dumps, loads  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402
from langchain_core.outputs import ChatGeneration, Generation  # noqa: E402

from placewise.llm_cache import cacheable  # noqa: E402


def _gen(tool_calls=True, stop="tool_use"):
    calls = [{"name": "MatchAssessment", "args": {"summary": "ok"}, "id": "t1", "type": "tool_call"}] if tool_calls else []
    return ChatGeneration(message=AIMessage(content="", tool_calls=calls, response_metadata={"stop_reason": stop}))


def test_only_complete_structured_answers_are_cached():
    assert cacheable([_gen()])
    assert not cacheable([_gen(tool_calls=False)])          # model skipped the tool: a failure, never replay it
    assert not cacheable([_gen(stop="max_tokens")])         # cut off
    assert not cacheable([Generation(text="plain")])
    assert not cacheable([])


def test_cached_generations_round_trip_with_tool_calls():
    back = loads(dumps([_gen()]))
    assert back[0].message.tool_calls[0]["args"] == {"summary": "ok"}


def test_a_replayed_response_costs_nothing():
    u = {"input_tokens": 2000, "output_tokens": 600, "total_cost": 0}
    c = usage_cost("claude-sonnet-5-5", u)
    assert c["usd"] == 0 and c["response_cache"] is True
    assert usage_cost("claude-sonnet-5-5", {"input_tokens": 2000, "output_tokens": 600})["response_cache"] is False


def test_malformed_structured_answer_is_not_cached():
    from pydantic import BaseModel

    class MatchAssessment(BaseModel):   # same name as the tool, a required field
        summary: str
        score_hint: int

    assert not cacheable([_gen()], MatchAssessment)        # args {"summary": "ok"}: missing score_hint
    good = ChatGeneration(message=AIMessage(content="", tool_calls=[{"name": "MatchAssessment", "id": "t",
        "args": {"summary": "ok", "score_hint": 3}, "type": "tool_call"}], response_metadata={"stop_reason": "tool_use"}))
    assert cacheable([good], MatchAssessment)

    class Other(BaseModel):
        summary: str
    assert not cacheable([good], Other)                     # a different tool name never matches
