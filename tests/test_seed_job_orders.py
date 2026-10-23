"""Block 1: job-order answer key (job_orders.label / targeted candidates). In memory only."""
import collections

import pytest

from placewise.seed import job_orders as J
from placewise.seed.facts import Credential

from seed_helpers import make_facts

JO1 = next(j for j in J.SPECS if j.job_order_id == "JO-01")   # civil, TX PE, 10+ yrs, DFW, transport, software
JO15 = next(j for j in J.SPECS if j.job_order_id == "JO-15")


def jo1_fit(**over):
    base = dict(years_experience=12.0, sectors=["transportation"], software=["Civil 3D"])
    base.update(over)
    return make_facts(**base)


def test_strong_when_all_requirements_met():
    lab = J.label(jo1_fit(), JO1)
    assert lab["grade"] == "strong"
    assert all(ch["met"] for ch in lab["checks"])


def test_partial_for_one_non_critical_miss():
    lab = J.label(jo1_fit(sectors=["aviation"]), JO1)
    assert lab["grade"] == "partial"
    assert [ch["kind"] for ch in lab["checks"] if not ch["met"]] == ["sector_any"]


def test_none_for_two_non_critical_misses():
    assert J.label(jo1_fit(sectors=["aviation"], software=["AutoCAD"]), JO1)["grade"] == "none"


def test_none_for_wrong_state_pe():
    c = jo1_fit(credentials=[Credential(key="PE", state="OK", number="1", text="P.E., Oklahoma #1")])
    assert J.label(c, JO1)["grade"] == "none"


def test_pursuing_or_expired_pe_does_not_satisfy():
    for status in ("pursuing", "expired"):
        c = jo1_fit(credentials=[Credential(key="PE", state="TX", status=status, counts=False, text="x")])
        assert J.label(c, JO1)["grade"] == "none", status


def test_metro_satisfied_by_relocation():
    c = jo1_fit(city="Houston", metro="Houston", open_to_relocation=True)
    assert J.label(c, JO1)["grade"] == "strong"
    c2 = jo1_fit(city="Houston", metro="Houston", open_to_relocation=False)
    assert J.label(c2, JO1)["grade"] == "none"


def test_years_near_miss_is_partial_but_far_miss_is_none():
    assert J.label(jo1_fit(years_experience=9.0), JO1)["grade"] == "partial"
    assert J.label(jo1_fit(years_experience=7.0), JO1)["grade"] == "none"


def test_accept_alternative_license():
    jo2 = next(j for j in J.SPECS if j.job_order_id == "JO-02")   # EIT or PE in TX
    c = make_facts(years_experience=5.0, software=["Civil 3D"])   # holds PE:TX
    assert J.label(c, jo2)["grade"] == "strong"


def test_unknown_requirement_kind_raises():
    with pytest.raises(ValueError):
        J.check_req(make_facts(), J.Req(kind="bogus"))


def test_targeted_candidates_answer_key():
    targeted = J.targeted_candidates(start_index=1, seed=42)
    for c in targeted:
        jo_id, kind = c.targets_job_order.split(":")
        jo = next(j for j in J.SPECS if j.job_order_id == jo_id)
        grade = J.label(c, jo)["grade"]
        if kind == "strong":
            assert grade == "strong", c.candidate_id
        else:
            assert grade != "strong", (c.candidate_id, kind)
    strong = collections.Counter(c.targets_job_order.split(":")[0] for c in targeted
                                 if c.targets_job_order.endswith(":strong"))
    assert all(strong[j.job_order_id] >= 4 for j in J.SPECS if not j.expect_no_match)
    assert strong["JO-15"] == 0


def test_jo15_has_no_strong_match_in_generated_pool():
    from placewise.seed import facts as F
    pool = F.generate(300, seed=42) + J.targeted_candidates(start_index=301, seed=42)
    assert not any(J.label(c, JO15)["grade"] == "strong" for c in pool)
