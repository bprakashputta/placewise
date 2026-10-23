"""Block 2: the extraction wrapper with a fake model (no network, no API key)."""
import asyncio

import pytest

from placewise.ingest import extract as ex
from placewise.ingest.schema import ExtractedProfile

PROFILE = ExtractedProfile.model_validate({
    "full_name": "Sam Synthetic", "headline": "Project Architect", "discipline": "architecture",
    "jobs": [{"title": "Architect", "employer": "Acme", "start": "2019", "end": "Present"}],
    "writing_quality": {"rating": "good"}})


class Raw:
    def __init__(self, i=100, o=50):
        self.usage_metadata = {"input_tokens": i, "output_tokens": o}


class ApiError(Exception):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class FakeModel:
    def __init__(self, script):
        self.script = list(script)
        self.calls = 0
        self.messages = None

    async def ainvoke(self, messages, config=None):
        self.calls += 1
        self.messages = messages
        step = self.script.pop(0)
        if isinstance(step, BaseException):
            raise step
        return step


@pytest.fixture
def fake(monkeypatch):
    def _install(*script):
        m = FakeModel(script)
        monkeypatch.setattr(ex, "_model", lambda model_id: m)
        return m
    return _install


def run(text="resume text", **kw):
    return asyncio.run(ex.extract(text, model_id="claude-sonnet-5-5", **kw))


def test_success_first_try(fake):
    m = fake({"raw": Raw(1000, 500), "parsed": PROFILE, "parsing_error": None})
    r = run()
    assert r.profile == PROFILE and r.attempts == 1 and r.problems == [] and m.calls == 1
    assert (r.input_tokens, r.output_tokens) == (1000, 500)
    assert r.cost_usd == pytest.approx(1000 / 1e6 * 2.0 + 500 / 1e6 * 10.0)


def test_schema_failure_then_retry_succeeds_and_tokens_summed(fake):
    m = fake({"raw": Raw(100, 10), "parsed": None, "parsing_error": "missing field jobs"},
             {"raw": Raw(100, 20), "parsed": PROFILE, "parsing_error": None})
    r = run()
    assert r.profile == PROFILE and r.attempts == 2 and r.problems == [] and m.calls == 2
    assert (r.input_tokens, r.output_tokens) == (200, 30)


def test_schema_failure_every_time_returns_problems(fake):
    fake(*[{"raw": Raw(), "parsed": None, "parsing_error": "bad"}] * 2)
    r = run()
    assert r.profile is None and r.attempts == 2 and r.problems and r.problems[0].startswith("schema:")


def test_4xx_stops_immediately(fake):
    m = fake(ApiError(400), {"raw": Raw(), "parsed": PROFILE})
    r = run()
    assert r.profile is None and m.calls == 1 and r.attempts == 1 and "api error" in r.problems[0]


def test_429_retries(fake):
    m = fake(ApiError(429), {"raw": Raw(), "parsed": PROFILE, "parsing_error": None})
    r = run()
    assert r.profile == PROFILE and m.calls == 2


def test_5xx_and_timeouts_retry_then_give_up_without_raising(fake):
    m = fake(ApiError(529), TimeoutError("read timeout"))
    r = run()
    assert r.profile is None and m.calls == 2 and "TimeoutError" in r.problems[0]


def test_missing_usage_metadata_is_tolerated(fake):
    class NoUsage:
        usage_metadata = None
    fake({"raw": NoUsage(), "parsed": PROFILE})
    r = run()
    assert r.profile == PROFILE and r.input_tokens == 0


def test_unknown_model_costs_zero_not_crash():
    assert ex.Extraction(profile=None, model="mystery", input_tokens=10).cost_usd == 0


def test_resume_text_truncated_and_in_user_message(fake):
    m = fake({"raw": Raw(), "parsed": PROFILE})
    run("A" * 50000 + "TAILMARKER")
    user = m.messages[1].content
    assert "TAILMARKER" not in user and "AAAA" in user
