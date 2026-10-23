"""Block 1: factcheck.check, writer.structural_check, resume_schema, and write_one with a mocked model.
No real LLM calls."""
import asyncio

import pytest

from placewise.seed import facts as F
from placewise.seed import writer
from placewise.seed.facts import Credential
from placewise.seed.factcheck import check
from placewise.seed.resume_schema import ResumeSection, StructuredResume
from placewise.seed.writer import structural_check

from seed_helpers import make_facts, make_resume


# ----------------------------------------------------------------------------- factcheck.check

def test_check_passes_correct_text():
    c = make_facts()
    assert check(make_resume(c).to_text(), c) == []


def test_check_flags_missing_credential_string():
    c = make_facts()
    text = make_resume(c).to_text().replace("P.E., Texas #123456", "Licensed engineer")
    probs = check(text, c)
    assert any("missing exact text" in p and "P.E., Texas #123456" in p for p in probs)


def test_check_flags_invented_pmp():
    c = make_facts()
    text = make_resume(c).to_text() + "\nPMP certified project lead"
    probs = check(text, c)
    assert any("invented credential" in p and "PMP" in p for p in probs)


def test_check_does_not_flag_engineer_in_training_title():
    c = make_facts()  # has the title "Civil Engineer in Training" but no EIT credential
    assert not any(cr.key == "EIT" for cr in c.credentials)
    assert check(make_resume(c).to_text(), c) == []


def test_pursuing_pe_does_not_exempt_other_pe_mentions():
    c = make_facts(credentials=[Credential(key="PE", status="pursuing", counts=False,
                                           text="Preparing for the PE exam")])
    base = make_resume(c).to_text()
    assert check(base, c) == []
    probs = check(base + "\nLicensed P.E. with 8 years of design experience", c)
    assert any("invented credential" in p and "(PE)" in p for p in probs)


def test_check_flags_commentary():
    c = make_facts()
    assert "contains commentary or code fences" in check("Here is the resume:\n" + make_resume(c).to_text(), c)


def test_check_tolerates_whitespace_and_dash_variants():
    c = make_facts()
    text = make_resume(c).to_text().replace("Testy Fixture", "Testy   Fixture")
    assert check(text, c) == []


def test_check_and_structural_pass_for_generated_candidates():
    """Property-style: a resume built straight from the facts must pass for every generated candidate."""
    for c in F.generate(120, seed=7):
        r = make_resume(c)
        assert check(r.to_text(), c) == [], c.candidate_id
        assert structural_check(r, c) == [], c.candidate_id


# ----------------------------------------------------------------------------- writer.structural_check

def test_structural_passes_correct_resume():
    c = make_facts()
    assert structural_check(make_resume(c), c) == []


def test_structural_flags_wrong_title_and_date():
    c = make_facts()
    r = make_resume(c)
    r.jobs[0].title = "Project Manager"
    r.jobs[1].start = "June 2018"
    probs = structural_check(r, c)
    assert any("job 1 title" in p for p in probs)
    assert any("job 2 start" in p for p in probs)


def test_structural_flags_wrong_job_count():
    c = make_facts()
    r = make_resume(c)
    r.jobs = r.jobs[:1]
    assert any("exactly 2 jobs" in p for p in structural_check(r, c))


def test_structural_flags_wrong_credential_list():
    c = make_facts()
    r = make_resume(c, credentials=["P.E., Texas #123456", "LEED AP BD+C"])
    assert any("credentials must be exactly" in p for p in structural_check(r, c))
    r2 = make_resume(c, credentials=[])
    assert any("credentials must be exactly" in p for p in structural_check(r2, c))


def test_structural_flags_invented_software():
    c = make_facts()
    r = make_resume(c, skills=["Civil 3D", "MicroStation", "ETABS"])
    assert any("'ETABS'" in p for p in structural_check(r, c))


def test_structural_allows_revit_when_facts_have_revit_mep():
    c = make_facts(discipline="mep", subdiscipline="Mechanical", software=["Revit MEP", "AutoCAD MEP"])
    r = make_resume(c, skills=["Revit MEP", "AutoCAD MEP"], summary="Models systems in Revit for hospitals.")
    assert not any("software" in p for p in structural_check(r, c))


def test_structural_flags_relocation_claim_when_not_open():
    c = make_facts(open_to_relocation=False)
    r = make_resume(c, contact=[c.email, c.phone, "Dallas, TX", "Open to relocation"])
    assert any("relocation" in p for p in structural_check(r, c))
    r2 = make_resume(c, summary="Willing to relocate for the right role.")
    assert any("relocation" in p for p in structural_check(r2, c))


def test_structural_allows_relocation_when_open():
    c = make_facts(open_to_relocation=True)
    assert structural_check(make_resume(c), c) == []


def test_structural_does_not_flag_utility_relocation():
    c = make_facts(open_to_relocation=False)
    r = make_resume(c, summary="Managed utility relocation and drainage design for TxDOT corridors.")
    assert structural_check(r, c) == []


def test_structural_flags_wrong_education_and_name():
    c = make_facts()
    r = make_resume(c, name="Testy Fixtures")
    r.education[0].year = "2019"
    probs = structural_check(r, c)
    assert any("name must be exactly" in p for p in probs)
    assert any("education must be exactly" in p for p in probs)


def test_structural_flags_bullet_count():
    c = make_facts()
    r = make_resume(c)
    r.jobs[0].bullets = []
    assert any("bullets" in p for p in structural_check(r, c))


# ----------------------------------------------------------------------------- resume_schema

def test_extra_sections_flattens_nested_items():
    s = ResumeSection(heading="Selected Projects", items=[["A", "B"], "C", 4])
    assert s.items == ["A", "B", "C", "4"]


def test_structured_resume_validates_nested_extra_sections_and_renders():
    c = make_facts()
    data = make_resume(c).model_dump()
    data["extra_sections"] = [{"heading": "Selected Projects", "items": [["I-35 widening", "SH-121 bridge"]]}]
    r = StructuredResume.model_validate(data)
    assert r.extra_sections[0].items == ["I-35 widening", "SH-121 bridge"]
    assert "- SH-121 bridge" in r.to_text()


# ----------------------------------------------------------------------------- write_one with a mocked model

class FakeModel:
    """Stands in for ChatAnthropic.with_structured_output(..., include_raw=True)."""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    async def ainvoke(self, messages):
        self.calls.append(messages)
        out = self.outputs.pop(0)
        if isinstance(out, BaseException):
            raise out
        return out


class _Raw:
    usage_metadata = {"input_tokens": 100, "output_tokens": 50}


def _run(model, c, retries=2):
    return asyncio.run(writer.write_one(model, c, asyncio.Semaphore(1), max_retries=retries))


def test_write_one_retries_with_feedback_then_accepts():
    c = make_facts()
    bad = make_resume(c, credentials=[])
    good = make_resume(c)
    m = FakeModel([{"raw": _Raw(), "parsed": bad}, {"raw": _Raw(), "parsed": good}])
    res = _run(m, c)
    assert res.ok and res.attempts == 2 and res.problems == []
    assert res.input_tokens == 200 and res.output_tokens == 100
    assert "previous attempt failed" in m.calls[1][1].content
    assert res.cost_usd > 0


def test_write_one_rejects_after_max_retries():
    c = make_facts()
    bad = make_resume(c, skills=["ETABS"])
    m = FakeModel([{"raw": _Raw(), "parsed": bad}] * 3)
    res = _run(m, c)
    assert not res.ok and res.attempts == 3 and res.problems


def test_write_one_schema_failure_is_retried():
    c = make_facts()
    m = FakeModel([{"raw": _Raw(), "parsed": None, "parsing_error": "bad json"},
                   {"raw": _Raw(), "parsed": make_resume(c)}])
    res = _run(m, c)
    assert res.ok and res.attempts == 2


def test_write_one_permanent_4xx_stops_without_retry():
    class BadRequest(Exception):
        status_code = 400

    c = make_facts()
    m = FakeModel([BadRequest("invalid"), {"raw": _Raw(), "parsed": make_resume(c)}])
    res = _run(m, c)
    assert not res.ok and res.attempts == 1 and "api error" in res.problems[0]


def test_write_one_429_is_retried(monkeypatch):
    class RateLimited(Exception):
        status_code = 429

    async def no_sleep(_):
        return None

    monkeypatch.setattr(writer.asyncio, "sleep", no_sleep)
    c = make_facts()
    m = FakeModel([RateLimited("slow down"), {"raw": _Raw(), "parsed": make_resume(c)}])
    res = _run(m, c)
    assert res.ok and res.attempts == 2


def test_writer_facts_do_not_leak_answer_key():
    c = make_facts(tricky=["pursuing_pe"], split="dev", targets_job_order="JO-01:strong")
    d = writer.facts_for_writer(c)
    flat = repr(d)
    for leak in ("split", "tricky", "license_codes", "targets_job_order", "quality", "JO-01", "pursuing_pe"):
        assert leak not in flat


@pytest.mark.parametrize("cid", ["C9001"])
def test_build_messages_loads_prompt(cid):
    msgs = writer.build_messages(make_facts(candidate_id=cid))
    assert len(msgs) == 2 and "Testy Fixture" in msgs[1].content
