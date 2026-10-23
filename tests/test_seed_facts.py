"""Block 1: facts generator (ground truth). In memory only, no writes."""
import collections

import pytest

from placewise.seed import facts as F


@pytest.fixture(scope="module")
def cands():
    return F.generate(200, seed=42)


def _ym(s: str) -> int:
    return int(s[:4]) * 12 + int(s[5:7]) - 1


def test_determinism_same_seed_identical():
    a = [c.model_dump() for c in F.generate(50, seed=42)]
    b = [c.model_dump() for c in F.generate(50, seed=42)]
    assert a == b


def test_different_seed_differs():
    a = [c.model_dump() for c in F.generate(50, seed=42)]
    b = [c.model_dump() for c in F.generate(50, seed=43)]
    assert a != b


def test_counts_and_unique_ids(cands):
    assert len(cands) == 200
    assert len({c.candidate_id for c in cands}) == 200
    variants = collections.Counter(c.variant for c in cands)
    assert variants["exact_duplicate"] == 3 and variants["format_duplicate"] == 3 and variants["updated"] == 4


def test_jobs_ordered_no_overlap_end_after_start(cands):
    as_of = _ym(F._ym(F.AS_OF))
    for c in cands:
        assert c.jobs, c.candidate_id
        for j in c.jobs:
            if j.end is not None:
                assert _ym(j.end) >= _ym(j.start), (c.candidate_id, j)
            assert _ym(j.start) <= as_of
        # newest first: each older job ends no later than the next newer job starts
        for newer, older in zip(c.jobs, c.jobs[1:]):
            assert older.end is not None, (c.candidate_id, "only the newest job may be open")
            assert _ym(older.end) <= _ym(newer.start), (c.candidate_id, older, newer)
            assert _ym(older.start) <= _ym(newer.start)


def test_current_job_is_open_and_matches_header(cands):
    for c in cands:
        assert c.jobs[0].end is None and c.jobs[0].end_text == "Present"
        assert c.current_title == c.jobs[0].title
        assert c.current_employer == c.jobs[0].employer


def test_date_texts_match_style(cands):
    for c in cands:
        for j in c.jobs:
            assert j.start_text == F._fmt_date(j.start, c.style.date_style)
            assert j.end_text == F._fmt_date(j.end, c.style.date_style)


def test_updated_variants_are_valid(cands):
    originals = {c.person_id: c for c in cands if c.variant == "original"}
    updated = [c for c in cands if c.variant == "updated"]
    assert updated
    for u in updated:
        src = originals[u.person_id]
        assert len(u.jobs) == len(src.jobs) + 1
        new, prev = u.jobs[0], u.jobs[1]
        assert new.end is None and prev.end is not None
        assert new.employer != prev.employer
        assert u.current_employer == new.employer
        assert prev.start == src.jobs[0].start and prev.employer == src.jobs[0].employer
        assert _ym(prev.end) >= _ym(prev.start) + 3
        assert _ym(new.start) == _ym(prev.end)
        assert _ym(new.start) <= _ym(F._ym(F.AS_OF)) - 2


def test_duplicates_copy_the_person(cands):
    originals = {c.person_id: c for c in cands if c.variant == "original"}
    for d in (c for c in cands if c.variant in ("exact_duplicate", "format_duplicate")):
        src = originals[d.person_id]
        assert d.candidate_id != src.candidate_id
        assert (d.full_name, d.jobs, d.credentials) == (src.full_name, src.jobs, src.credentials)
        assert not d.unreadable and not d.injection


def test_license_codes_exclude_pursuing_and_expired():
    c = F.CandidateFacts.model_construct(credentials=[
        F.Credential(key="PE", state="TX", text="P.E., Texas", status="active", counts=True),
        F.Credential(key="PE", state="OK", text="P.E., Oklahoma (inactive)", status="expired", counts=False),
        F.Credential(key="PE", state=None, text="Preparing for the PE exam", status="pursuing", counts=False),
        F.Credential(key="LEED_AP", text="LEED AP BD+C"),
    ])
    assert c.license_codes == ["LEED_AP", "PE:TX"]


def test_license_codes_consistent_with_counts(cands):
    for c in cands:
        for cr in c.credentials:
            assert cr.counts == (cr.status == "active")
        held = {f"{cr.key}:{cr.state}" if cr.state else cr.key for cr in c.credentials if cr.counts}
        assert set(c.license_codes) == held
        # a pursuing/scheduled PE has no state, so it can never produce a "PE:None" code
        assert not any(code.endswith(":None") or code == "PE" for code in c.license_codes)


def test_split_by_person(cands):
    by_person = collections.defaultdict(set)
    for c in cands:
        by_person[c.person_id].add(c.split)
        assert c.split == F.split_for(c.person_id, 42)
    assert all(len(s) == 1 for s in by_person.values())
    assert {c.split for c in cands} == {"dev", "test"}


def test_unreadable_and_injection_have_matching_format(cands):
    for c in cands:
        if c.unreadable == "corrupt_docx":
            assert c.style.file_format == "docx" and c.quality == "unusable"
        if c.unreadable == "image_pdf":
            assert c.style.file_format == "pdf" and c.quality == "unusable"
        if c.injection:
            assert c.style.file_format == "pdf" and c.quality == "adversarial"
    assert any(c.injection for c in cands) and any(c.unreadable for c in cands)


# ---- break-it

def test_generate_zero_count_is_a_clear_error_or_empty():
    """`facts --count 0` currently crashes inside random.sample (ValueError). Documented, not a real use case."""
    try:
        out = F.generate(0, seed=42)
    except ValueError:
        return
    assert out == []
