"""Synthetic candidate facts: the ground truth.

Code (not an LLM) decides every fact, with a fixed random seed, so:
- the same seed always produces the same candidates (reproducible), and
- we know the correct answer for every field, which is what makes evals possible.

Credential phrasing variants ("P.E., Texas #123456" vs "Licensed PE (TX)") are also
chosen here by code. The resume writer must copy them exactly, so messiness in the
critical facts comes from code, not from the model that later reads the resumes.
"""
from __future__ import annotations

import hashlib
import random
from datetime import date
from typing import Literal

from faker import Faker
from pydantic import BaseModel, Field

from . import catalog as C

AS_OF = date(2026, 10, 22)  # fixed "today" so output never depends on when it runs

STATE_NAMES = {"TX": "Texas", "OK": "Oklahoma", "LA": "Louisiana", "AR": "Arkansas", "CO": "Colorado",
               "AZ": "Arizona", "GA": "Georgia", "IL": "Illinois", "NM": "New Mexico"}
AREA_CODES = {"DFW": ["214", "469", "972", "817"], "Houston": ["713", "281", "832"], "Austin": ["512", "737"],
              "San Antonio": ["210", "726"], "Other": ["405", "918", "318", "225", "501", "303", "602", "404"]}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTHS_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
               "October", "November", "December"]


# ----------------------------------------------------------------------------- models

class Credential(BaseModel):
    key: str                      # PE, EIT, RA, NCIDQ, TX_RID, SE, NCARB, LEED_AP, LEED_GA, PMP, CCM, OSHA_30
    state: str | None = None
    status: Literal["active", "expired", "pursuing", "exam_scheduled"] = "active"
    number: str | None = None
    text: str                     # exact phrase the resume must contain
    counts: bool = True           # does the person actually hold it? (False for pursuing/expired)


class Project(BaseModel):
    name: str
    sector: str
    value_usd: int | None = None
    role: str


class Job(BaseModel):
    title: str
    employer: str
    city: str
    state: str
    start: str                    # YYYY-MM
    end: str | None = None        # YYYY-MM, None = current
    start_text: str               # pre-formatted in this resume's date style; must appear verbatim
    end_text: str
    projects: list[Project] = []


class Education(BaseModel):
    degree: str
    school: str
    year: int


class Style(BaseModel):
    template: Literal["classic", "modern", "two_column", "ats_plain", "compact"]
    persona: Literal["concise", "narrative", "senior_exec", "junior_academic", "technical_detail", "messy"]
    length: Literal["short", "medium", "long"]
    file_format: Literal["pdf", "docx", "txt"]
    header_style: Literal["standard", "caps", "unusual"]
    date_style: Literal["Mon YYYY", "MM/YYYY", "Month YYYY", "YYYY", "MM/YY"]


class CandidateFacts(BaseModel):
    synthetic: bool = True
    candidate_id: str
    person_id: str
    variant: Literal["original", "exact_duplicate", "format_duplicate", "updated"] = "original"
    first_name: str
    last_name: str
    email: str
    phone: str
    city: str
    state: str
    metro: str
    open_to_relocation: bool
    discipline: str
    subdiscipline: str | None = None
    years_experience: float
    current_title: str | None
    current_employer: str | None
    jobs: list[Job]
    credentials: list[Credential] = []
    software: list[str] = []
    sectors: list[str] = []
    education: list[Education] = []
    desired_salary: int
    availability: Literal["active", "passive"]
    last_contacted: str | None = None   # YYYY-MM-DD, for bench-revival later
    style: Style
    tricky: list[str] = []
    injection: bool = False
    unreadable: Literal["image_pdf", "corrupt_docx"] | None = None
    split: Literal["dev", "test"] = "test"
    targets_job_order: str | None = None  # set when generated to satisfy a job order
    quality: Literal["polished", "flawed", "unusable", "adversarial"] = "polished"
    quality_issues: list[str] = []      # e.g. ["typos", "poorly_written"]: deliberate, so evals can check detection

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def license_codes(self) -> list[str]:
        """Credentials actually held, e.g. ['PE:TX', 'LEED_AP']. The answer key uses these."""
        return sorted({f"{c.key}:{c.state}" if c.state else c.key for c in self.credentials if c.counts})


class Constraints(BaseModel):
    """Used to generate candidates that satisfy (or nearly satisfy) a specific job order."""
    discipline: str | None = None
    subdiscipline: str | None = None
    metro: str | None = None
    min_years: float | None = None
    max_years: float | None = None
    credentials: list[tuple[str, str | None]] = Field(default_factory=list)  # (key, state)
    software: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    open_to_relocation: bool | None = None


# ----------------------------------------------------------------------------- helpers

def _weighted(rng: random.Random, weights: dict) -> str:
    keys = list(weights)
    vals = [w[0] if isinstance(w, tuple) else w for w in weights.values()]
    return rng.choices(keys, weights=vals, k=1)[0]


def _level(years: float) -> int:
    return next(level for max_y, level in C.LEVELS if years <= max_y)


def _ym(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _months_back(months: int) -> date:
    total = AS_OF.year * 12 + (AS_OF.month - 1) - months
    return date(total // 12, total % 12 + 1, 1)


def _fmt_date(ym: str | None, style: str) -> str:
    if ym is None:
        return "Present"
    y, m = int(ym[:4]), int(ym[5:7])
    return {
        "Mon YYYY": f"{MONTHS[m - 1]} {y}",
        "MM/YYYY": f"{m:02d}/{y}",
        "Month YYYY": f"{MONTHS_LONG[m - 1]} {y}",
        "YYYY": f"{y}",
        "MM/YY": f"{m:02d}/{y % 100:02d}",
    }[style]


def _cred_text(rng: random.Random, key: str, state: str | None, status: str, number: str | None) -> str:
    sn = STATE_NAMES.get(state or "", state or "")
    if status == "pursuing":
        return rng.choice(["Preparing for the PE exam", "Pursuing Professional Engineer licensure",
                           "Working toward PE licensure"]) if key == "PE" else \
               rng.choice(["Pursuing architectural licensure (ARE in progress)", "Completing the ARE"])
    if status == "exam_scheduled":
        when = f"{rng.choice(MONTHS)} {AS_OF.year + 1}"
        return f"PE exam scheduled for {when}" if key == "PE" else f"Final ARE division scheduled for {when}"
    suffix = " (inactive)" if status == "expired" else ""
    variants = {
        "PE": [f"P.E., {sn} #{number}", f"Professional Engineer ({state}), License No. {number}",
               f"Licensed PE - {sn}", f"PE ({state} #{number})", f"Registered Professional Engineer, State of {sn}"],
        "EIT": [f"E.I.T. ({sn})", f"Engineer in Training (EIT), {sn}", f"EIT Certification - {sn}"],
        "RA": [f"Registered Architect, {sn} #{number}", f"Licensed Architect ({state})",
               f"Registered Architect - State of {sn}"],
        "SE": [f"S.E., {sn}", f"Structural Engineer (SE), State of {sn}"],
        "NCARB": ["NCARB Certificate"],
        "NCIDQ": [f"NCIDQ Certificate #{number}", "NCIDQ Certified"],
        "TX_RID": [f"Registered Interior Designer, Texas (RID #{number})"],
        "LEED_AP": ["LEED AP BD+C", "LEED Accredited Professional (BD+C)"],
        "LEED_GA": ["LEED Green Associate", "LEED GA"],
        "PMP": ["PMP", "Project Management Professional (PMP)"],
        "CCM": ["Certified Construction Manager (CCM)"],
        "OSHA_30": ["OSHA 30-Hour Construction", "OSHA 30"],
    }[key]
    return rng.choice(variants) + suffix


def _cred(rng, key, state=None, status="active", discipline: str | None = None) -> Credential:
    number = str(rng.randint(100000, 159999)) if key in ("PE", "RA", "NCIDQ", "TX_RID") else None
    text = _cred_text(rng, key, state, status, number)
    if key == "LEED_AP" and discipline == "interior_design":
        text = rng.choice(["LEED AP ID+C", "LEED Accredited Professional (ID+C)"])  # interiors specialty
    return Credential(key=key, state=state, status=status, number=number, text=text, counts=status == "active")


def _pick_state(rng, home_state: str) -> str:
    if home_state != "TX" and rng.random() < 0.6:
        return home_state
    return "TX" if rng.random() < 0.88 else rng.choice(["OK", "LA", "AR", "CO", "NM"])


# ----------------------------------------------------------------------------- generator

def make_candidate(rng: random.Random, fake: Faker, cid: str, pid: str,
                   cons: Constraints | None = None) -> CandidateFacts:
    cons = cons or Constraints()
    discipline = cons.discipline or _weighted(rng, C.DISCIPLINE_WEIGHTS)
    metro = cons.metro or _weighted(rng, C.METROS)
    city, state = rng.choice(C.METROS[metro][1])
    sub = cons.subdiscipline or (rng.choice(C.SUBDISCIPLINES[discipline]) if discipline in C.SUBDISCIPLINES else None)

    lo = cons.min_years if cons.min_years is not None else 0.5
    hi = cons.max_years if cons.max_years is not None else 32
    years = round(min(max(rng.triangular(0.5, 30, 3), lo), hi) * 2) / 2
    level = _level(years)

    # Titles by career track
    if discipline == "construction_management" and sub == "field operations":
        titles = C.CM_FIELD_TITLES
    elif discipline == "construction_management" and sub == "estimating":
        titles = C.CM_ESTIMATING_TITLES
    else:
        titles = [t.format(sub=sub) for t in C.TITLES[discipline]]

    # Jobs: split the career into 1-5 stints, newest first, current job open-ended
    total_months = max(int(years * 12), 6)
    n_jobs = max(1, min(5, 1 + int(years // rng.uniform(3.5, 6))))
    cuts = sorted(rng.sample(range(3, total_months), k=n_jobs - 1)) if n_jobs > 1 and total_months > n_jobs * 3 else []
    if not cuts:
        n_jobs = 1
    bounds = [0, *cuts, total_months]              # months from career start
    firms = rng.sample(C.FIRMS[discipline], k=min(n_jobs, len(C.FIRMS[discipline])))
    while len(firms) < n_jobs:
        firms.append(rng.choice(C.FIRMS[discipline]))

    my_sectors = list(dict.fromkeys(cons.sectors + rng.sample(C.SECTORS[discipline], k=rng.randint(2, 3))))[:4]
    jobs_oldest_first: list[Job] = []
    used_projects: set[str] = set()
    for j in range(n_jobs):
        start = _months_back(total_months - bounds[j])
        end = None if j == n_jobs - 1 else _months_back(total_months - bounds[j + 1])
        yrs_at_start = bounds[j] / 12
        title = titles[_level(yrs_at_start + 0.01) if j < n_jobs - 1 else level]
        jcity, jstate = (city, state) if (j == n_jobs - 1 or rng.random() < 0.7) else rng.choice(
            [c for m in C.METROS.values() for c in m[1]])
        projects = []
        for _ in range(rng.randint(1, 3)):
            for _attempt in range(6):  # keep project names unique within one resume
                sector = rng.choice(my_sectors)
                ptype = rng.choice(C.PROJECT_TYPES.get(sector, ["Facility"]))
                place = rng.choice(C.METROS[metro][1])[0] if rng.random() < 0.8 else jcity
                name = f"{place} ISD {ptype.replace('ISD ', '')}" if ptype.startswith("ISD") else f"{place} {ptype}"
                if name not in used_projects:
                    break
            else:
                continue
            used_projects.add(name)
            projects.append(Project(name=name, sector=sector,
                                    value_usd=rng.choice([None, rng.randint(3, 450) * 1_000_000]),
                                    role=title))
        jobs_oldest_first.append(Job(title=title, employer=firms[j], city=jcity, state=jstate,
                                     start=_ym(start), end=_ym(end) if end else None,
                                     start_text="", end_text="", projects=projects))
    jobs = list(reversed(_split_promotions(jobs_oldest_first, titles, total_months)))

    # Credentials (realistic base rates by discipline and seniority)
    creds: list[Credential] = []
    lic_state = _pick_state(rng, state)
    if discipline in ("civil", "structural", "mep"):
        if years < 4:
            if rng.random() < 0.8:
                creds.append(_cred(rng, "EIT", lic_state))
        elif rng.random() < 0.78:
            creds.append(_cred(rng, "PE", lic_state))
            if rng.random() < 0.12:
                creds.append(_cred(rng, "PE", rng.choice(["OK", "LA", "AR", "NM"])))
        else:
            if rng.random() < 0.6:
                creds.append(_cred(rng, "EIT", lic_state))
            if years <= 9 and rng.random() < 0.45:   # mid-career engineers often list PE progress
                creds.append(_cred(rng, "PE", None, rng.choice(["pursuing", "exam_scheduled"])))
        if discipline == "structural" and years >= 8 and rng.random() < 0.15:
            creds.append(_cred(rng, "SE", "IL"))
        if rng.random() < 0.15:
            creds.append(_cred(rng, "LEED_AP"))
        if level >= 3 and rng.random() < 0.12:
            creds.append(_cred(rng, "PMP"))
    elif discipline == "architecture":
        if years >= 3 and rng.random() < 0.62:
            creds.append(_cred(rng, "RA", lic_state))
            if rng.random() < 0.2:
                creds.append(_cred(rng, "NCARB"))
        r = rng.random()
        if r < 0.3:
            creds.append(_cred(rng, "LEED_AP"))
        elif r < 0.45:
            creds.append(_cred(rng, "LEED_GA"))
    elif discipline == "interior_design":
        if years >= 3 and rng.random() < 0.5:
            creds.append(_cred(rng, "NCIDQ"))
            if state == "TX" and rng.random() < 0.5:
                creds.append(_cred(rng, "TX_RID", "TX"))
        r = rng.random()
        if r < 0.25:
            creds.append(_cred(rng, "LEED_AP", discipline="interior_design"))
        elif r < 0.4:
            creds.append(_cred(rng, "LEED_GA"))
    else:  # construction management
        if rng.random() < 0.7:
            creds.append(_cred(rng, "OSHA_30"))
        if years >= 5 and rng.random() < 0.2:
            creds.append(_cred(rng, "PMP"))
        if years >= 8 and rng.random() < 0.08:
            creds.append(_cred(rng, "CCM"))
        if rng.random() < 0.15:
            creds.append(_cred(rng, "LEED_AP"))

    # Forced credentials from constraints (replace any same-key credential)
    for key, cstate in cons.credentials:
        creds = [c for c in creds if c.key != key and not (key == "PE" and c.key == "EIT")]
        creds.append(_cred(rng, key, cstate))

    software = list(dict.fromkeys(cons.software + rng.sample(C.SOFTWARE[discipline], k=rng.randint(3, 6))))
    deg_options = [d for d in C.DEGREES[discipline] if d[1] in (None, sub)]
    degree = rng.choice(deg_options)[0]
    school = rng.choice(C.UNIVERSITIES["TX" if state == "TX" or rng.random() < 0.6 else "other"])
    grad_year = int(jobs[-1].start[:4]) - rng.choice([0, 0, 1])
    education = [Education(degree=degree, school=school, year=grad_year)]

    first, last = fake.first_name(), fake.last_name()
    lo_sal, hi_sal = C.SALARY_BY_LEVEL[level]
    style = _style(rng, years)
    for job in jobs:
        job.start_text = _fmt_date(job.start, style.date_style)
        job.end_text = _fmt_date(job.end, style.date_style)

    return CandidateFacts(
        candidate_id=cid, person_id=pid,
        first_name=first, last_name=last,
        email=f"{first}.{last}{rng.randint(1, 99)}@example.com".lower().replace("'", ""),
        phone=f"({rng.choice(AREA_CODES[metro])}) 555-01{rng.randint(0, 99):02d}",
        city=city, state=state, metro=metro,
        open_to_relocation=cons.open_to_relocation if cons.open_to_relocation is not None else rng.random() < 0.3,
        discipline=discipline, subdiscipline=sub, years_experience=years,
        current_title=jobs[0].title, current_employer=jobs[0].employer,
        jobs=jobs, credentials=creds, software=software, sectors=my_sectors, education=education,
        desired_salary=round(rng.randint(lo_sal, hi_sal) / 5000) * 5000,
        availability="active" if rng.random() < 0.3 else "passive",
        last_contacted=None if rng.random() < 0.4 else (_months_back(rng.randint(1, 36))).isoformat(),
        style=style,
    )


def _split_promotions(jobs: list[Job], titles: list[str], total_months: int) -> list[Job]:
    """Split a stint wherever the person crossed a career level, so titles progress
    realistically within the same employer (e.g. Project Engineer → Project Manager)."""
    career_start = _months_back(total_months)
    cs = career_start.year * 12 + career_start.month - 1

    def idx(ym: str | None) -> int:
        if ym is None:
            return AS_OF.year * 12 + AS_OF.month - 1
        return int(ym[:4]) * 12 + int(ym[5:7]) - 1

    def ym_of(i: int) -> str:
        return f"{i // 12:04d}-{i % 12 + 1:02d}"

    boundaries = [int(max_y * 12) for max_y, _ in C.LEVELS[:-1]]  # months of experience where level changes
    out: list[Job] = []
    for job in jobs:
        a, b = idx(job.start), idx(job.end)
        cuts = [cs + m for m in boundaries if a + 6 < cs + m < b - 6]
        if not cuts:
            job.title = titles[_level((b - cs) / 12)]
            out.append(job)
            continue
        edges = [a, *cuts, b]
        for k in range(len(edges) - 1):
            seg_end = None if (job.end is None and k == len(edges) - 2) else ym_of(edges[k + 1])
            lvl = _level((edges[k + 1] - cs) / 12 - 0.01)
            out.append(job.model_copy(update={
                "title": titles[lvl], "start": ym_of(edges[k]), "end": seg_end,
                "projects": job.projects if k == len(edges) - 2 else [],
            }))
    return out[-7:]  # cap entries; drop the oldest if a long career produced many


def _style(rng: random.Random, years: float) -> Style:
    length = "short" if years < 3 else ("long" if years > 15 and rng.random() < 0.6 else rng.choice(["short", "medium", "medium"]))
    persona = "junior_academic" if years < 2 else ("senior_exec" if years > 18 and rng.random() < 0.5 else
                                                     rng.choice(["concise", "narrative", "technical_detail"]))
    return Style(
        template=rng.choice(["classic", "modern", "two_column", "ats_plain", "compact"]),
        persona=persona, length=length,
        file_format=rng.choices(["pdf", "docx", "txt"], weights=[60, 30, 10])[0],
        header_style=rng.choices(["standard", "caps", "unusual"], weights=[60, 25, 15])[0],
        date_style=rng.choice(["Mon YYYY", "MM/YYYY", "Month YYYY", "YYYY", "MM/YY"]),
    )


def recompute_years(c: "CandidateFacts") -> None:
    """Years of experience = what the resume's dated jobs actually show (gaps excluded, overlaps merged).
    Keeps the answer key consistent with the resume after truncation or gap edits."""
    now = AS_OF.year * 12 + AS_OF.month - 1
    spans = sorted((int(j.start[:4]) * 12 + int(j.start[5:7]) - 1,
                    now if j.end is None else int(j.end[:4]) * 12 + int(j.end[5:7]) - 1) for j in c.jobs)
    total, cur_s, cur_e = 0, None, None
    for a, b in spans:
        if cur_e is None or a > cur_e:
            if cur_e is not None:
                total += cur_e - cur_s
            cur_s, cur_e = a, b
        else:
            cur_e = max(cur_e, b)
    if cur_e is not None:
        total += cur_e - cur_s
    c.years_experience = round(total / 12 * 2) / 2


# ----------------------------------------------------------------------------- tricky cases

def apply_tricky(rng: random.Random, c: CandidateFacts) -> CandidateFacts:
    """Turn a normal candidate into an edge case that is applicable to them."""
    engineering = c.discipline in ("civil", "structural", "mep")
    options = ["career_gap", "short_resume", "long_resume", "unusual_headers", "two_column", "typos"]
    held_pe = any(x.key == "PE" and x.counts for x in c.credentials)
    if engineering and held_pe:
        options += ["out_of_state_pe", "expired_license"] * 2
    if engineering and 3 <= c.years_experience <= 8 and not any(x.key == "PE" for x in c.credentials):
        options += ["pursuing_pe"] * 3
    if any(x.key == "LEED_AP" for x in c.credentials):
        options += ["leed_ga_not_ap"]
    kind = rng.choice(options)

    if kind == "out_of_state_pe":
        st = rng.choice(["OK", "LA", "AR", "NM"])
        c.credentials = [_cred(rng, "PE", st) if (x.key == "PE" and x.counts) else x for x in c.credentials]
        c.credentials = list({(x.key, x.state): x for x in c.credentials}.values())
    elif kind == "expired_license":
        c.credentials = [_cred(rng, "PE", x.state, "expired") if (x.key == "PE" and x.counts) else x
                         for x in c.credentials]
    elif kind == "pursuing_pe":
        c.credentials = [x for x in c.credentials if x.key != "EIT"] + [
            _cred(rng, "EIT", c.state if c.state in STATE_NAMES else "TX"),
            _cred(rng, "PE", None, rng.choice(["pursuing", "exam_scheduled"]))]
    elif kind == "leed_ga_not_ap":
        c.credentials = [_cred(rng, "LEED_GA") if x.key == "LEED_AP" else x for x in c.credentials]
    elif kind == "career_gap" and len(c.jobs) < 2:
        kind = "short_resume"
    elif kind == "career_gap":
        # Shift the previous job's end back 12-18 months to leave a visible gap
        prev = c.jobs[1]
        y, m = int(prev.end[:4]), int(prev.end[5:7])
        total = y * 12 + m - 1 - rng.randint(12, 18)
        start_total = int(prev.start[:4]) * 12 + int(prev.start[5:7]) - 1
        if total > start_total + 3:
            prev.end = f"{total // 12:04d}-{total % 12 + 1:02d}"
            prev.end_text = _fmt_date(prev.end, c.style.date_style)
        else:
            kind = "short_resume"
    if kind == "short_resume":
        c.style.length = "short"
    elif kind == "long_resume":
        c.style.length = "long"
    elif kind == "unusual_headers":
        c.style.header_style = "unusual"
    elif kind == "two_column":
        c.style.template, c.style.file_format = "two_column", "pdf"
    c.tricky.append(kind)
    return c


# ----------------------------------------------------------------------------- dataset

def split_for(person_id: str, seed: int) -> str:
    """Stable dev/test split by PERSON, so duplicates of one person never straddle splits."""
    h = int(hashlib.sha256(f"{seed}:{person_id}".encode()).hexdigest(), 16)
    return "dev" if h % 10 < 3 else "test"


def generate(count: int, seed: int = 42) -> list[CandidateFacts]:
    rng = random.Random(seed)
    fake = Faker("en_US")
    fake.seed_instance(seed)

    n_exact = round(count * 0.015)
    n_format = round(count * 0.015)
    n_updated = round(count * 0.02)
    n_base = count - n_exact - n_format - n_updated

    people: list[CandidateFacts] = []
    for i in range(n_base):
        c = make_candidate(rng, fake, cid=f"C{i + 1:04d}", pid=f"P{i + 1:04d}")
        if rng.random() < 0.15:
            c = apply_tricky(rng, c)
        people.append(c)

    # Security and robustness cases on distinct base candidates
    pool = rng.sample(range(n_base), k=max(1, round(count * 0.01)) + 2 * max(1, round(count * 0.008)))
    n_inj = max(1, round(count * 0.01))
    for idx in pool[:n_inj]:
        people[idx].injection = True
        people[idx].tricky.append("prompt_injection")
        people[idx].style.file_format = "pdf"
    n_unr = max(1, round(count * 0.008))
    for idx in pool[n_inj:n_inj + n_unr]:
        people[idx].unreadable, people[idx].style.file_format = "image_pdf", "pdf"
        people[idx].tricky.append("unreadable_image_pdf")
    for idx in pool[n_inj + n_unr:]:
        people[idx].unreadable, people[idx].style.file_format = "corrupt_docx", "docx"
        people[idx].tricky.append("unreadable_corrupt_docx")

    # Duplicates and updates reference readable, non-adversarial originals
    eligible = [p for p in people if not p.unreadable and not p.injection]
    extras: list[CandidateFacts] = []
    next_id = n_base + 1
    for variant, n in (("exact_duplicate", n_exact), ("format_duplicate", n_format), ("updated", n_updated)):
        made = 0
        for src in rng.sample(eligible, k=len(eligible)):
            if made == n:
                break
            dup = src.model_copy(deep=True)
            if variant == "updated" and not _add_new_job(rng, dup):
                continue  # current job too new to have changed already; pick someone else
            dup.candidate_id, dup.variant = f"C{next_id:04d}", variant
            next_id += 1
            made += 1
            if variant == "format_duplicate":
                dup.style.template = rng.choice([t for t in ["classic", "modern", "ats_plain", "compact"]
                                                 if t != src.style.template])
                dup.style.file_format = "docx" if src.style.file_format != "docx" else "pdf"
            dup.tricky = [*dup.tricky, variant]
            extras.append(dup)
    # Deliberately poorly written resumes (~8%), so "bad" is always intentional and labeled
    for c in people:
        if not c.unreadable and not c.injection and rng.random() < 0.08:
            c.style.persona = "messy"
            c.tricky.append("poorly_written")
            if rng.random() < 0.6:
                c.tricky.append("typos")
    # Duplicates were copied before the messy pass: re-sync style/flags from their source so the
    # answer key matches the resume text they reuse (exact/format duplicates share the source's text).
    src_by_person = {p.person_id: p for p in people}
    for d in extras:
        src = src_by_person[d.person_id]
        if d.variant in ("exact_duplicate", "format_duplicate"):
            d.style.persona = src.style.persona
            d.tricky = [t for t in src.tricky] + [d.variant]
    allc = people + extras
    for c in allc:
        c.split = split_for(c.person_id, seed)
        recompute_years(c)
        label_quality(c)
    return allc


FLAW_KINDS = {"typos", "poorly_written", "short_resume", "unusual_headers", "career_gap"}


def label_quality(c: CandidateFacts) -> None:
    """Answer-key label for resume quality. The ingest pipeline should detect these on its own."""
    if c.unreadable:
        c.quality, c.quality_issues = "unusable", ["image_only_pdf" if c.unreadable == "image_pdf" else "corrupt_file"]
    elif c.injection:
        c.quality, c.quality_issues = "adversarial", ["prompt_injection"]
    else:
        issues = sorted(set(c.tricky) & FLAW_KINDS)
        c.quality, c.quality_issues = ("flawed", issues) if issues else ("polished", [])


def _add_new_job(rng: random.Random, c: CandidateFacts) -> bool:
    """The person changed jobs recently: close the current job and add a new one.
    Returns False if the current job is too new to have been left already."""
    from . import catalog as cat
    cur = c.jobs[0]
    cur_start = int(cur.start[:4]) * 12 + int(cur.start[5:7]) - 1
    now = AS_OF.year * 12 + AS_OF.month - 1
    earliest_end, latest_end = cur_start + 3, now - 2
    if earliest_end > latest_end:
        return False
    end_i = rng.randint(max(earliest_end, now - 9), latest_end)
    to_ym = lambda i: f"{i // 12:04d}-{i % 12 + 1:02d}"  # noqa: E731
    cur.end, cur.end_text = to_ym(end_i), _fmt_date(to_ym(end_i), c.style.date_style)
    employer = rng.choice([f for f in cat.FIRMS[c.discipline] if f != cur.employer])
    new = Job(title=cur.title, employer=employer, city=c.city, state=c.state, start=to_ym(end_i), end=None,
              start_text=_fmt_date(to_ym(end_i), c.style.date_style), end_text="Present", projects=[])
    c.jobs.insert(0, new)
    c.current_employer = employer
    return True
