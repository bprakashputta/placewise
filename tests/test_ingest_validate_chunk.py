"""Block 2: code validation/normalization after extraction, and chunking/blind text."""
from datetime import date

import pytest

from placewise.ingest.chunk import blind_text, build_chunks
from placewise.ingest.schema import ExtractedProfile
from placewise.ingest.screen import Screen
from placewise.ingest.validate import (has_gap, norm_sectors, norm_software, parse_date, state_code, validate,
                                       years_from_dates)

TODAY = date(2026, 10, 22)


def profile(**over) -> ExtractedProfile:
    base = {
        "full_name": "Jordan Q Sample", "email": "jordan.sample@example.com", "phone": "(214) 555-0100",
        "city": "Plano", "state": "Texas", "headline": "Senior Civil Engineer", "discipline": "civil",
        "summary": "Roadway and drainage engineer.",
        "jobs": [{"title": "Project Engineer", "employer": "Acme Civil", "start": "Jan 2016", "end": "Dec 2019",
                  "highlights": ["Designed drainage for 40 lane-miles"]},
                 {"title": "Senior Engineer", "employer": "Beta Engineers", "start": "Jan 2020", "end": "Present",
                  "highlights": ["Led TxDOT schematic"]}],
        "credentials": [{"quote": "Professional Engineer (PE), Texas", "key": "PE", "state": "Texas",
                         "status": "active"}],
        "software": ["civil 3d"], "sectors": ["Transportation"],
        "education": [{"degree": "BS Civil Engineering", "school": "Texas Tech University", "year": "2015"}],
        "writing_quality": {"rating": "good", "issues": []},
    }
    base.update(over)
    return ExtractedProfile.model_validate(base)


RESUME = ("Jordan Q Sample\nSenior Civil Engineer, Plano, Texas\nProfessional Engineer (PE), Texas\n"
          "LEED AP BD+C\nEIT, Oklahoma (pursuing PE)\nPE – Colorado (expired)\n")


def clean_screen(**kw):
    return Screen(kw.get("quality", "polished"), kw.get("issues", []), RESUME, [])


def jobs(*spans):
    return [{"title": "T", "employer": f"E{i}", "start": a, "end": b} for i, (a, b) in enumerate(spans)]


# ---------- parse_date ----------
@pytest.mark.parametrize("s,expected", [
    ("Jan 2019", (2019, 1)), ("January 2019", (2019, 1)), ("Sept. 2019", (2019, 9)), ("dec 2020", (2020, 12)),
    ("01/2019", (2019, 1)), ("1/2019", (2019, 1)), ("01/19", (2019, 1)), ("12/99", (1999, 12)),
    ("2019", (2019, 6)), ("Present", (2026, 10)), ("current", (2026, 10)), ("  NOW ", (2026, 10)),
    (None, None), ("", None), ("unknown", None),
])
def test_parse_date_formats(s, expected):
    assert parse_date(s, TODAY) == expected


# ---------- years / gaps ----------
def test_years_sequential_jobs():
    p = profile(jobs=jobs(("Jan 2016", "Jan 2020"), ("Jan 2020", "Jan 2024")))
    assert years_from_dates(p, TODAY) == 8.0


def test_years_overlaps_counted_once():
    p = profile(jobs=jobs(("Jan 2010", "Jan 2020"), ("Jan 2015", "Jan 2018"), ("Jun 2019", "Jan 2022")))
    assert years_from_dates(p, TODAY) == 12.0


def test_years_gaps_not_counted():
    p = profile(jobs=jobs(("Jan 2010", "Jan 2012"), ("Jan 2015", "Jan 2017")))
    assert years_from_dates(p, TODAY) == 4.0


def test_years_open_end_is_today_and_unparseable_ignored():
    p = profile(jobs=[{"title": "T", "employer": "E", "start": "Oct 2016", "end": None},
                      {"title": "T", "employer": "F", "start": "sometime", "end": "later"}])
    assert years_from_dates(p, TODAY) == 10.0


def test_years_none_when_no_dates_and_inverted_spans_dropped():
    assert years_from_dates(profile(jobs=jobs((None, None))), TODAY) is None
    assert years_from_dates(profile(jobs=jobs(("Jan 2020", "Jan 2018"))), TODAY) is None


def test_has_gap():
    assert has_gap(profile(jobs=jobs(("Jan 2010", "Jan 2012"), ("Jan 2013", "Jan 2015"))), TODAY)  # 12 months
    assert not has_gap(profile(jobs=jobs(("Jan 2010", "Jan 2012"), ("Jun 2012", "Jan 2015"))), TODAY)  # 5 months
    # an overlapping long job covers a later short gap
    assert not has_gap(profile(jobs=jobs(("Jan 2010", "Jan 2020"), ("Jan 2012", "Jan 2013"),
                                         ("Jan 2015", "Jan 2016"))), TODAY)


# ---------- normalization ----------
@pytest.mark.parametrize("raw,code", [("Texas", "TX"), ("tx", "TX"), (" new mexico ", "NM"), ("Nowhere", None),
                                      (None, None)])
def test_state_code(raw, code):
    assert state_code(raw) == code


def test_metro_mapping_and_state_normalized():
    v = validate(profile(city="Plano", state="Texas"), RESUME, clean_screen(), TODAY)
    assert v.metro == "DFW" and v.profile["state"] == "TX"
    assert validate(profile(city=" houston ", state="TX"), RESUME, clean_screen(), TODAY).metro == "Houston"
    assert validate(profile(city="Plano", state="IL"), RESUME, clean_screen(), TODAY).metro == "Other"
    assert validate(profile(city=None, state=None), RESUME, clean_screen(), TODAY).metro == "Other"


def test_software_and_sector_normalization():
    assert norm_software(["civil 3d", "Civil3D", "REVIT", "Some Tool"]) == ["Civil 3D", "Revit", "Some Tool"]
    out = norm_sectors(["Transportation", "data center campus", "K12", "Hospital", "unrelated"])
    assert out[0] == "transportation"
    assert "mission critical / data centers" in out and "K-12 education" in out and "healthcare" in out
    assert len(out) == len(set(out))


# ---------- credentials ----------
def test_credential_quote_missing_from_text_is_dropped():
    p = profile(credentials=[
        {"quote": "Professional Engineer (PE), Texas", "key": "PE", "state": "Texas", "status": "active"},
        {"quote": "Structural Engineer (SE), Illinois", "key": "SE", "state": "IL", "status": "active"}])
    v = validate(p, RESUME, clean_screen(), TODAY)
    assert v.license_codes == ["PE:TX"]
    assert any("Structural Engineer" in n for n in v.notes)
    assert all(c["key"] != "SE" for c in v.profile["credentials"])


def test_credential_quote_matches_despite_dash_and_whitespace_differences():
    p = profile(credentials=[{"quote": "PE - Colorado   (expired)", "key": "PE", "state": "CO", "status": "expired"}])
    v = validate(p, RESUME, clean_screen(), TODAY)
    assert len(v.profile["credentials"]) == 1  # en dash in the resume vs hyphen in the quote


def test_license_codes_exclude_pursuing_expired_and_other():
    p = profile(credentials=[
        {"quote": "Professional Engineer (PE), Texas", "key": "PE", "state": "Texas", "status": "active"},
        {"quote": "LEED AP BD+C", "key": "LEED_AP", "state": "TX", "status": "active"},
        {"quote": "EIT, Oklahoma (pursuing PE)", "key": "PE", "state": "OK", "status": "pursuing"},
        {"quote": "PE – Colorado (expired)", "key": "PE", "state": "Colorado", "status": "expired"},
        {"quote": "Jordan Q Sample", "key": "OTHER", "state": None, "status": "active"}])
    v = validate(p, RESUME, clean_screen(), TODAY)
    assert v.license_codes == ["LEED_AP", "PE:TX"]  # LEED is not state-keyed: its state is dropped


# ---------- quality merge ----------
def test_quality_polished():
    assert validate(profile(), RESUME, clean_screen(), TODAY).quality == "polished"


def test_quality_flawed_from_writing_or_gap():
    poor = profile(writing_quality={"rating": "poor", "issues": ["typos"]})
    v = validate(poor, RESUME, clean_screen(), TODAY)
    assert v.quality == "flawed" and {"poorly_written", "typos"} <= set(v.quality_issues)
    gap = profile(jobs=jobs(("Jan 2010", "Jan 2012"), ("Jan 2014", "Present")))
    v = validate(gap, RESUME, clean_screen(), TODAY)
    assert v.quality == "flawed" and "career_gap" in v.quality_issues


def test_quality_typos_ignored_when_rating_good():
    v = validate(profile(writing_quality={"rating": "good", "issues": ["typos"]}), RESUME, clean_screen(), TODAY)
    assert v.quality == "polished" and "typos" not in v.quality_issues


def test_quality_screen_flawed_issue_carries_over():
    v = validate(profile(), RESUME, clean_screen(quality="flawed", issues=["very_short"]), TODAY)
    assert v.quality == "flawed" and "very_short" in v.quality_issues


def test_quality_adversarial_beats_everything():
    scr = clean_screen(quality="adversarial", issues=["prompt_injection", "hidden_text", "very_short"])
    v = validate(profile(writing_quality={"rating": "poor", "issues": []}), RESUME, scr, TODAY)
    assert v.quality == "adversarial"


def test_quality_unusable_beats_flawed():
    v = validate(profile(writing_quality={"rating": "poor", "issues": []}), RESUME,
                 clean_screen(quality="unusable", issues=["corrupt_file"]), TODAY)
    assert v.quality == "unusable"


def test_hidden_text_alone_does_not_make_flawed_after_validate():
    # documents current behavior: the screen labels hidden_text-only as flawed, validate does not
    v = validate(profile(), RESUME, clean_screen(quality="flawed", issues=["hidden_text"]), TODAY)
    assert "hidden_text" in v.quality_issues


# ---------- chunk / blind ----------
def _validated_profile():
    return validate(profile(), RESUME, clean_screen(), TODAY).profile


def test_chunks_have_no_name_email_phone():
    chunks = build_chunks(_validated_profile())
    assert {c["section"] for c in chunks} >= {"summary", "job", "credentials", "skills", "education"}
    assert [c["ordinal"] for c in chunks] == list(range(len(chunks)))
    for c in chunks:
        low = c["content"].lower()
        assert "jordan" not in low and "sample" not in low
        assert "example.com" not in low and "555" not in low and "0100" not in low
        assert c["content"].startswith("[Senior Civil Engineer | civil]")


def test_blind_text_excludes_identity_and_graduation_year():
    t = blind_text(_validated_profile())
    assert "Jordan" not in t and "Sample" not in t and "example.com" not in t and "555" not in t
    assert "2015" not in t                       # graduation year
    assert "Texas Tech" not in t                 # school name omitted too
    assert "Plano" not in t                      # location
    assert "BS Civil Engineering" in t and "Acme Civil" in t


def test_chunks_skip_empty_sections():
    p = _validated_profile()
    p.update(summary=None, credentials=[], software=[], sectors=[], education=[])
    assert {c["section"] for c in build_chunks(p)} == {"job"}
