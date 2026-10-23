"""Synthetic job orders, targeted candidates, and the matching answer key.

- 15 job-order SPECS (hand-designed, realistic for A/E/C recruiting; clients described generically).
- For each, targeted candidates: strong fits plus near misses (one critical requirement fails), so
  ranking quality can be measured, not just "found something".
- The answer key labels every (job order, candidate) pair strong / partial / none, with the reason
  for each requirement.
"""
from __future__ import annotations

import random

from faker import Faker
from pydantic import BaseModel, Field

from .facts import CandidateFacts, Constraints, label_quality, make_candidate, recompute_years, split_for


class Req(BaseModel):
    kind: str            # discipline | subdiscipline | license | years | metro | software_any | sector_any | cert
    value: str | float | list[str] | None = None
    state: str | None = None
    accept: list[str] = Field(default_factory=list)   # alternative license keys that also satisfy (e.g. EIT or PE)
    critical: bool = True                              # a miss on a critical requirement means "none"
    text: str = ""                                     # plain-English wording, used in the notes prompt


class JobOrderSpec(BaseModel):
    job_order_id: str
    title: str
    client: str
    city: str
    metro: str
    work_mode: str
    employment_type: str
    salary: str
    must_have: list[Req]
    nice_to_have: list[Req] = []
    omit_in_notes: list[str] = []    # details deliberately left out of the call notes → clarifying questions
    split: str = "test"
    expect_no_match: bool = False
    synthetic: bool = True


def R(kind, value=None, text="", **kw) -> Req:
    return Req(kind=kind, value=value, text=text, **kw)


SPECS: list[JobOrderSpec] = [
    JobOrderSpec(job_order_id="JO-01", title="Senior Civil Project Manager - Transportation",
                 client="Mid-size civil engineering firm (Frisco office)", city="Frisco", metro="DFW",
                 work_mode="hybrid", employment_type="direct_hire", salary="$150k-$175k",
                 must_have=[R("discipline", "civil", "civil engineer"), R("license", "PE", "Texas PE", state="TX"),
                            R("years", 10, "10+ years"), R("metro", "DFW", "DFW-based or relocating"),
                            R("sector_any", ["transportation"], "transportation / roadway work", critical=False),
                            R("software_any", ["MicroStation", "OpenRoads Designer", "Civil 3D", "GEOPAK"],
                              "MicroStation/OpenRoads or Civil 3D", critical=False)],
                 nice_to_have=[R("cert", "PMP", "PMP")], omit_in_notes=["work_mode"]),
    JobOrderSpec(job_order_id="JO-02", title="Civil Project Engineer - Land Development",
                 client="Land development engineering consultant (Plano)", city="Plano", metro="DFW",
                 work_mode="onsite", employment_type="direct_hire", salary="$85k-$105k", split="dev",
                 must_have=[R("discipline", "civil", "civil engineer"),
                            R("license", "EIT", "EIT or PE in Texas", state="TX", accept=["PE"]),
                            R("years", 3, "3+ years"), R("metro", "DFW", "DFW"),
                            R("software_any", ["Civil 3D"], "Civil 3D", critical=False)],
                 omit_in_notes=["salary"]),
    JobOrderSpec(job_order_id="JO-03", title="Drainage / Hydraulics Engineer",
                 client="Water resources group of a national consultant (Houston)", city="Houston", metro="Houston",
                 work_mode="hybrid", employment_type="direct_hire", salary="$115k-$140k",
                 must_have=[R("discipline", "civil", "civil engineer"), R("license", "PE", "Texas PE", state="TX"),
                            R("years", 6, "6+ years"), R("metro", "Houston", "Houston"),
                            R("software_any", ["HEC-RAS", "HEC-HMS"], "HEC-RAS / HEC-HMS", critical=False),
                            R("sector_any", ["drainage and flood control", "water/wastewater"], "drainage work",
                              critical=False)]),
    JobOrderSpec(job_order_id="JO-04", title="Structural Project Engineer",
                 client="Structural engineering firm (Dallas)", city="Dallas", metro="DFW", work_mode="hybrid",
                 employment_type="direct_hire", salary="$110k-$135k",
                 must_have=[R("discipline", "structural", "structural engineer"),
                            R("license", "PE", "Texas PE", state="TX"), R("years", 5, "5+ years"),
                            R("metro", "DFW", "DFW"),
                            R("software_any", ["ETABS", "RAM Structural System", "RISA-3D"], "ETABS / RAM / RISA",
                              critical=False)],
                 nice_to_have=[R("sector_any", ["healthcare", "commercial office"], "healthcare or office")],
                 omit_in_notes=["employment_type"]),
    JobOrderSpec(job_order_id="JO-05", title="Senior Structural Engineer",
                 client="Structural consultant (Austin office)", city="Austin", metro="Austin", work_mode="onsite",
                 employment_type="direct_hire", salary="$135k-$160k",
                 must_have=[R("discipline", "structural", "structural engineer"),
                            R("license", "PE", "Texas PE", state="TX"), R("years", 8, "8+ years"),
                            R("metro", "Austin", "Austin"),
                            R("sector_any", ["parking structures", "commercial office", "multifamily"],
                              "parking / commercial / multifamily", critical=False)]),
    JobOrderSpec(job_order_id="JO-06", title="Electrical Engineer - Mission Critical",
                 client="MEP engineering firm (Irving)", city="Irving", metro="DFW", work_mode="hybrid",
                 employment_type="direct_hire", salary="$125k-$155k", split="dev",
                 must_have=[R("discipline", "mep", "MEP engineer"), R("subdiscipline", "Electrical", "electrical"),
                            R("license", "PE", "Texas PE", state="TX"), R("years", 6, "6+ years"),
                            R("metro", "DFW", "DFW"),
                            R("sector_any", ["mission critical / data centers"], "data center experience",
                              critical=False),
                            R("software_any", ["ETAP", "SKM PowerTools"], "ETAP or SKM", critical=False)],
                 omit_in_notes=["work_mode", "salary"]),
    JobOrderSpec(job_order_id="JO-07", title="Mechanical Project Engineer - Healthcare",
                 client="MEP consultant (Dallas)", city="Dallas", metro="DFW", work_mode="hybrid",
                 employment_type="contract_to_hire", salary="$95k-$115k",
                 must_have=[R("discipline", "mep", "MEP engineer"), R("subdiscipline", "Mechanical", "mechanical"),
                            R("license", "EIT", "EIT or PE", state=None, accept=["PE"]), R("years", 3, "3+ years"),
                            R("metro", "DFW", "DFW"),
                            R("sector_any", ["healthcare"], "healthcare projects", critical=False),
                            R("software_any", ["Revit MEP"], "Revit MEP", critical=False)]),
    JobOrderSpec(job_order_id="JO-08", title="Project Architect - K-12 Education",
                 client="Architecture firm (Fort Worth)", city="Fort Worth", metro="DFW", work_mode="onsite",
                 employment_type="direct_hire", salary="$95k-$120k",
                 must_have=[R("discipline", "architecture", "architect"),
                            R("license", "RA", "Texas registered architect", state="TX"), R("years", 6, "6+ years"),
                            R("metro", "DFW", "DFW"),
                            R("sector_any", ["K-12 education"], "K-12 school projects", critical=False),
                            R("software_any", ["Revit"], "Revit", critical=False)],
                 omit_in_notes=["salary"]),
    JobOrderSpec(job_order_id="JO-09", title="Healthcare Architect / Associate",
                 client="Healthcare-focused architecture firm (Houston)", city="Houston", metro="Houston",
                 work_mode="hybrid", employment_type="direct_hire", salary="$140k-$170k", split="dev",
                 must_have=[R("discipline", "architecture", "architect"),
                            R("license", "RA", "Texas registered architect", state="TX"), R("years", 12, "12+ years"),
                            R("metro", "Houston", "Houston"),
                            R("sector_any", ["healthcare"], "healthcare", critical=False)]),
    JobOrderSpec(job_order_id="JO-10", title="Senior Interior Designer - Corporate Workplace",
                 client="Design firm (Dallas)", city="Dallas", metro="DFW", work_mode="hybrid",
                 employment_type="direct_hire", salary="$95k-$120k",
                 must_have=[R("discipline", "interior_design", "interior designer"),
                            R("license", "NCIDQ", "NCIDQ"), R("years", 6, "6+ years"), R("metro", "DFW", "DFW"),
                            R("sector_any", ["corporate workplace"], "corporate workplace", critical=False),
                            R("software_any", ["Revit"], "Revit", critical=False)],
                 nice_to_have=[R("license", "TX_RID", "Texas RID", state="TX")]),
    JobOrderSpec(job_order_id="JO-11", title="Interior Designer - Hospitality",
                 client="Hospitality design studio (Austin)", city="Austin", metro="Austin", work_mode="onsite",
                 employment_type="contract", salary="$40-$50/hr",
                 must_have=[R("discipline", "interior_design", "interior designer"), R("years", 3, "3+ years"),
                            R("metro", "Austin", "Austin"),
                            R("sector_any", ["hospitality"], "hospitality", critical=False),
                            R("software_any", ["Revit", "AutoCAD"], "Revit or AutoCAD", critical=False)],
                 nice_to_have=[R("license", "NCIDQ", "NCIDQ")], omit_in_notes=["employment_type"]),
    JobOrderSpec(job_order_id="JO-12", title="Project Manager - Healthcare (General Contractor)",
                 client="Commercial general contractor (Dallas)", city="Dallas", metro="DFW", work_mode="onsite",
                 employment_type="direct_hire", salary="$140k-$170k + bonus", split="dev",
                 must_have=[R("discipline", "construction_management", "construction PM"),
                            R("subdiscipline", "project management", "project management track"),
                            R("years", 8, "8+ years"), R("metro", "DFW", "DFW"),
                            R("sector_any", ["healthcare"], "healthcare builds", critical=False),
                            R("software_any", ["Procore"], "Procore", critical=False)],
                 nice_to_have=[R("cert", "PMP", "PMP"), R("cert", "OSHA_30", "OSHA 30")]),
    JobOrderSpec(job_order_id="JO-13", title="Superintendent - Industrial / Data Center",
                 client="General contractor (DFW)", city="Fort Worth", metro="DFW", work_mode="onsite",
                 employment_type="direct_hire", salary="$130k-$160k + truck",
                 must_have=[R("discipline", "construction_management", "construction"),
                            R("subdiscipline", "field operations", "field / superintendent track"),
                            R("years", 10, "10+ years"), R("metro", "DFW", "DFW"),
                            R("cert", "OSHA_30", "OSHA 30"),
                            R("sector_any", ["industrial", "mission critical / data centers"],
                              "industrial or data center", critical=False)]),
    JobOrderSpec(job_order_id="JO-14", title="Senior Estimator - Commercial",
                 client="General contractor (San Antonio)", city="San Antonio", metro="San Antonio",
                 work_mode="onsite", employment_type="direct_hire", salary="$110k-$135k",
                 must_have=[R("discipline", "construction_management", "construction"),
                            R("subdiscipline", "estimating", "estimating track"), R("years", 7, "7+ years"),
                            R("metro", "San Antonio", "San Antonio"),
                            R("software_any", ["On-Screen Takeoff", "Sage 300 CRE"], "OST or Sage",
                              critical=False)],
                 omit_in_notes=["salary"]),
    JobOrderSpec(job_order_id="JO-15", title="Principal Structural Engineer - Sports Venues",
                 client="Structural engineering firm (Dallas)", city="Dallas", metro="DFW", work_mode="onsite",
                 employment_type="direct_hire", salary="$220k-$260k", split="dev", expect_no_match=True,
                 must_have=[R("discipline", "structural", "structural engineer"),
                            R("license", "SE", "SE license (Illinois)", state="IL"),
                            R("license", "PE", "Texas PE", state="TX"), R("years", 20, "20+ years"),
                            R("metro", "DFW", "DFW"),
                            R("sector_any", ["sports and entertainment"], "stadium / arena projects"),
                            R("software_any", ["Tekla Structures"], "Tekla")]),
]


# ----------------------------------------------------------------------------- answer key

def _has_license(c: CandidateFacts, req: Req) -> bool:
    keys = [req.value, *req.accept]
    return any(cr.counts and cr.key in keys and (req.state is None or cr.state == req.state) for cr in c.credentials)


def check_req(c: CandidateFacts, req: Req) -> tuple[bool, str]:
    k = req.kind
    if k == "discipline":
        ok = c.discipline == req.value
        return ok, f"discipline {c.discipline}"
    if k == "subdiscipline":
        ok = (c.subdiscipline or "").lower() == str(req.value).lower()
        return ok, f"specialty {c.subdiscipline}"
    if k in ("license", "cert"):
        ok = _has_license(c, req)
        held = [f"{cr.key}:{cr.state}" if cr.state else cr.key for cr in c.credentials if cr.counts]
        return ok, f"holds {held or 'none'}"
    if k == "years":
        ok = c.years_experience >= float(req.value)
        return ok, f"{c.years_experience} yrs"
    if k == "metro":
        ok = c.metro == req.value or c.open_to_relocation
        return ok, f"{c.city} ({c.metro}){', open to relocation' if c.open_to_relocation else ''}"
    if k == "software_any":
        hit = [s for s in c.software if s in req.value]
        return bool(hit), f"software {hit or 'none of required'}"
    if k == "sector_any":
        hit = [s for s in c.sectors if s in req.value]
        return bool(hit), f"sectors {hit or 'none of required'}"
    raise ValueError(k)


def label(c: CandidateFacts, jo: JobOrderSpec) -> dict:
    checks = []
    for req in jo.must_have:
        ok, why = check_req(c, req)
        checks.append({"requirement": req.text or req.kind, "kind": req.kind, "critical": req.critical,
                       "met": ok, "why": why})
    misses = [x for x in checks if not x["met"]]
    critical_miss = any(x["critical"] for x in misses)
    years_req = next((r for r in jo.must_have if r.kind == "years"), None)
    near_years = (years_req is not None and len(misses) == 1 and misses[0]["kind"] == "years"
                  and c.years_experience >= float(years_req.value) - 1.0)
    if not misses:
        grade = "strong"
    elif (not critical_miss and len(misses) == 1) or near_years:
        grade = "partial"
    else:
        grade = "none"
    return {"job_order_id": jo.job_order_id, "candidate_id": c.candidate_id, "person_id": c.person_id,
            "grade": grade, "checks": checks}


# ----------------------------------------------------------------------------- targeted candidates

def _constraints_for(jo: JobOrderSpec, rng: random.Random, miss: str | None) -> Constraints:
    cons = Constraints(open_to_relocation=False)
    for req in jo.must_have:
        if req.kind == "discipline":
            cons.discipline = req.value
        elif req.kind == "subdiscipline":
            cons.subdiscipline = req.value
        elif req.kind == "license":
            if miss == "license":
                # Near miss: right credential, wrong state (or EIT instead of PE)
                if req.state == "TX":
                    cons.credentials.append((req.value, rng.choice(["OK", "LA", "AR", "NM"])))
                else:
                    pass  # simply missing
            else:
                state = req.state or ("TX" if req.value in ("PE", "EIT", "RA") else None)
                cons.credentials.append((req.value, state))
        elif req.kind == "cert":
            if miss != "cert":
                cons.credentials.append((req.value, None))
        elif req.kind == "years":
            y = float(req.value)
            if miss == "years":
                cons.min_years, cons.max_years = max(1.0, y - 2.5), max(1.5, y - 1.5)
            else:
                cons.min_years, cons.max_years = y, y + 8
        elif req.kind == "metro":
            if miss == "metro":
                cons.metro = rng.choice([m for m in ("DFW", "Houston", "Austin", "San Antonio") if m != req.value])
            else:
                cons.metro = req.value
        elif req.kind == "software_any" and miss != "software":
            cons.software = [rng.choice(req.value)]
        elif req.kind == "sector_any" and miss != "sector":
            cons.sectors = [rng.choice(req.value)]
    return cons


def targeted_candidates(start_index: int, seed: int) -> list[CandidateFacts]:
    rng = random.Random(seed + 1000)
    fake = Faker("en_US")
    fake.seed_instance(seed + 1000)
    out: list[CandidateFacts] = []
    i = start_index
    for jo in SPECS:
        kinds = {r.kind for r in jo.must_have}
        plan = [] if jo.expect_no_match else [None] * 4
        near = [k for k in ("license", "metro", "years") if k in kinds]
        plan += near[:3] if near else ["years"]
        for miss in plan:
            cid = f"C{i:04d}"
            c = make_candidate(rng, fake, cid=cid, pid=f"P{i:04d}", cons=_constraints_for(jo, rng, miss))
            if miss and miss == "license":
                # The near miss must not ALSO hold the right license through the random base rates
                lic = [r for r in jo.must_have if r.kind == "license"]
                bad_keys = {k for r in lic for k in [r.value, *r.accept]}
                bad_states = {r.state for r in lic}
                c.credentials = [cr for cr in c.credentials
                                 if not (cr.counts and cr.key in bad_keys and (None in bad_states or cr.state in bad_states))]
            c.targets_job_order = f"{jo.job_order_id}:{'strong' if miss is None else 'near_miss_' + miss}"
            c.split = split_for(c.person_id, seed)
            recompute_years(c)
            label_quality(c)
            out.append(c)
            i += 1
    return out
