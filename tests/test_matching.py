"""Blocks 4+6: matching logic without DB/LLM: hard filters, code verdicts, scoring, gating."""
from placewise.matching.engine import code_verdict, hard_filters, score
from placewise.matching.schema import JobSpec, Requirement, RequirementVerdict


def spec(**kw):
    reqs = kw.pop("requirements", None) or [
        Requirement(text="Civil engineer", kind="discipline", priority="must"),
        Requirement(text="Texas PE", kind="license", priority="must", key="PE", state="TX"),
        Requirement(text="10+ years", kind="years", priority="must", value="10"),
        Requirement(text="DFW or relocating", kind="location", priority="must"),
        Requirement(text="Transportation work", kind="sector", priority="nice"),
    ]
    return JobSpec(title="Sr Civil PM", metro="DFW", discipline="civil", min_years=10, requirements=reqs, **kw)


def prof(**kw):
    return {"license_codes": ["PE:TX"], "years_experience": 12, "metro": "DFW", "open_to_relocation": False,
            "discipline": "civil", **kw}


def test_hard_filters_strict_then_relaxed_steps():
    steps = hard_filters(spec())
    labels = [s[0] for s in steps]
    assert labels == ["strict", "years", "metro", "license"]
    strict = steps[0][1]
    assert strict.discipline == "civil" and strict.license_codes == ["PE:TX"] and strict.metro == "DFW"
    assert strict.min_years == 9          # one year of tolerance (scored 'partial' later)
    assert steps[-1][1].license_codes == [] and steps[-1][1].metro is None and steps[-1][1].min_years is None


def test_license_verdicts_by_code():
    s = spec()
    lic = s.requirements[1]
    assert code_verdict(lic, s, prof()).verdict == "met"
    out = code_verdict(lic, s, prof(license_codes=["PE:OK"]))
    assert out.verdict == "partial" and "another state" in out.note
    assert code_verdict(lic, s, prof(license_codes=["EIT:TX"])).verdict == "not_met"


def test_eit_or_pe_requirement_accepts_pe():
    r = Requirement(text="EIT or PE in Texas", kind="license", priority="must", key="EIT", state="TX")
    assert code_verdict(r, spec(), prof(license_codes=["PE:TX"])).verdict == "met"


def test_years_and_location_verdicts():
    s = spec()
    yrs, loc = s.requirements[2], s.requirements[3]
    assert code_verdict(yrs, s, prof(years_experience=10)).verdict == "met"
    assert code_verdict(yrs, s, prof(years_experience=9.5)).verdict == "partial"
    assert code_verdict(yrs, s, prof(years_experience=7)).verdict == "not_met"
    assert code_verdict(loc, s, prof(metro="DFW")).verdict == "met"
    assert code_verdict(loc, s, prof(metro="Houston", open_to_relocation=True)).verdict == "partial"
    assert code_verdict(loc, s, prof(metro="Houston")).verdict == "not_met"


def test_soft_requirements_left_to_llm():
    s = spec()
    assert code_verdict(s.requirements[4], s, prof()) is None


def v(text, verdict):
    return RequirementVerdict(requirement=text, verdict=verdict)


def test_score_weights_must_three_times_nice():
    s = spec()
    all_met = [v(r.text, "met") for r in s.requirements]
    assert score(s, all_met) == (100.0, "submit")
    nice_missing = all_met[:-1] + [v("Transportation work", "not_met")]
    sc, rec = score(s, nice_missing)          # 12/13 = 92.3
    assert round(sc, 1) == 92.3 and rec == "submit"


def test_missing_must_license_gates_to_pass():
    s = spec()
    verdicts = [v(r.text, "met") for r in s.requirements]
    verdicts[1] = v("Texas PE", "not_met")
    sc, rec = score(s, verdicts)
    assert sc <= 40 and rec == "pass"


def test_partial_license_is_consider_not_submit():
    s = spec()
    verdicts = [v(r.text, "met") for r in s.requirements]
    verdicts[1] = v("Texas PE", "partial")       # PE in another state
    sc, rec = score(s, verdicts)                  # 88.5 would be "submit" by score alone...
    assert sc == 88.5 and rec == "consider"       # ...but an out-of-state PE must be confirmed first


def test_relocating_candidate_is_consider_not_submit():
    s = spec()
    verdicts = [v(r.text, "met") for r in s.requirements]
    verdicts[3] = v("DFW or relocating", "partial")
    assert score(s, verdicts)[1] == "consider"


def test_unknown_counts_a_little():
    s = spec(requirements=[Requirement(text="Revit", kind="software", priority="must")])
    assert score(s, [v("Revit", "unknown")]) == (25.0, "pass")
