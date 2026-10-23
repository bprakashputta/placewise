"""Code checks and normalization after extraction. The LLM never has the final say on facts.

- Credentials: the quote must actually appear in the resume, or the credential is dropped.
- Years of experience: computed from the job dates by code (not by the model).
- States, metros, software and sectors: normalized to standard names so SQL filters work.
- Career gaps: detected from dates.
- Final quality label: screen findings (security, unreadable) + the model's writing assessment.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from ..seed import catalog  # shared A/E/C reference vocabulary (metros, software, sectors)
from .schema import ExtractedProfile
from .screen import Screen

STATES = {"texas": "TX", "oklahoma": "OK", "louisiana": "LA", "arkansas": "AR", "colorado": "CO",
          "arizona": "AZ", "georgia": "GA", "illinois": "IL", "new mexico": "NM", "kansas": "KS",
          "california": "CA", "florida": "FL", "new york": "NY"}
STATE_KEYED = {"PE", "EIT", "RA", "SE", "TX_RID"}
MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
                                          "nov", "dec"])}
CITY_TO_METRO = {(city.lower(), st): metro for metro, (_, cities) in catalog.METROS.items() for city, st in cities}
SOFTWARE = {s.lower(): s for tools in catalog.SOFTWARE.values() for s in tools}
SECTORS = sorted({s for v in catalog.SECTORS.values() for s in v}, key=len, reverse=True)
SECTOR_ALIASES = {"k-12": "K-12 education", "k12": "K-12 education", "data center": "mission critical / data centers",
                  "mission critical": "mission critical / data centers", "office": "commercial office",
                  "hotel": "hospitality", "apartment": "multifamily", "airport": "aviation", "aviation": "aviation",
                  "flood": "drainage and flood control", "drainage": "drainage and flood control",
                  "water": "water/wastewater", "wastewater": "water/wastewater", "roadway": "transportation",
                  "highway": "transportation", "university": "higher education", "campus": "higher education",
                  "hospital": "healthcare", "medical": "healthcare", "workplace": "corporate workplace",
                  "subdivision": "land development", "senior living": "senior living", "stadium": "sports and entertainment",
                  "arena": "sports and entertainment", "parking": "parking structures", "laborator": "laboratories",
                  "manufactur": "industrial", "distribution": "industrial", "warehouse": "industrial"}


@dataclass
class Validated:
    profile: dict                           # normalized profile (stored as JSONB)
    license_codes: list[str]
    software: list[str]
    sectors: list[str]
    years_experience: float | None
    metro: str
    quality: str
    quality_issues: list[str]
    notes: list[str] = field(default_factory=list)   # what validation changed or dropped, for the trace/UI


def _norm(s: str) -> str:
    s = s.replace("–", "-").replace("—", "-").replace(" ", " ").replace("’", "'")
    return re.sub(r"\s+", " ", s).strip().lower()


def state_code(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    if len(s) == 2 and s.isalpha():
        return s.upper()
    return STATES.get(s.lower())


def parse_date(s: str | None, today: date) -> tuple[int, int] | None:
    """'Jan 2019' | 'January 2019' | '01/2019' | '01/19' | '2019' | 'Present' → (year, month)."""
    if not s:
        return None
    t = s.strip().lower()
    if re.fullmatch(r"(present|current|now|today)", t):
        return today.year, today.month
    m = re.search(r"\b(\d{1,2})/(\d{4})\b", t)
    if m:
        return int(m.group(2)), int(m.group(1))
    m = re.search(r"\b(\d{1,2})/(\d{2})\b", t)
    if m:
        yy = int(m.group(2))
        return (2000 + yy if yy <= today.year % 100 + 1 else 1900 + yy), int(m.group(1))
    m = re.search(r"\b([a-z]{3})[a-z]*\.?\s+((?:19|20)\d{2})\b", t)
    if m and m.group(1) in MONTHS:
        return int(m.group(2)), MONTHS[m.group(1)]
    m = re.search(r"\b((?:19|20)\d{2})\b", t)
    if m:
        return int(m.group(1)), 6  # year only: mid-year on both ends keeps spans unbiased
    return None


def _spans(p: ExtractedProfile, today: date) -> list[tuple[int, int]]:
    out = []
    for j in p.jobs:
        a, b = parse_date(j.start, today), parse_date(j.end, today) if j.end else (today.year, today.month)
        if a and b:
            ai, bi = a[0] * 12 + a[1] - 1, b[0] * 12 + b[1] - 1
            if bi >= ai:
                out.append((ai, bi))
    return sorted(out)


def years_from_dates(p: ExtractedProfile, today: date) -> float | None:
    spans = _spans(p, today)
    if not spans:
        return None
    total, cs, ce = 0, spans[0][0], spans[0][1]
    for a, b in spans[1:]:
        if a > ce:
            total += ce - cs
            cs, ce = a, b
        else:
            ce = max(ce, b)
    total += ce - cs
    return round(total / 12 * 2) / 2


def has_gap(p: ExtractedProfile, today: date, months: int = 9) -> bool:
    spans = _spans(p, today)
    reach = None
    for a, b in spans:
        if reach is not None and a - reach >= months:
            return True
        reach = b if reach is None else max(reach, b)
    return False


def norm_software(items: list[str]) -> list[str]:
    out = []
    for s in items:
        canon = SOFTWARE.get(s.strip().lower())
        if canon is None:
            squashed = s.lower().replace(" ", "")
            canon = next((v for k, v in SOFTWARE.items() if k.replace(" ", "") == squashed), s.strip())
        if canon not in out:
            out.append(canon)
    return out


def norm_sectors(items: list[str]) -> list[str]:
    out = []
    for s in items:
        low = s.lower()
        canon = next((x for x in SECTORS if x.lower() == low), None) or \
            next((v for k, v in SECTOR_ALIASES.items() if k in low), None) or \
            next((x for x in SECTORS if x.lower() in low), None)
        if canon and canon not in out:
            out.append(canon)
    return out


def validate(p: ExtractedProfile, resume_text: str, scr: Screen, today: date | None = None) -> Validated:
    today = today or date.today()
    text = _norm(resume_text)
    notes: list[str] = []
    creds = []
    for c in p.credentials:
        if _norm(c.quote) not in text:
            notes.append(f"dropped credential not found in resume text: {c.quote!r}")
            continue
        st = state_code(c.state) if c.key in STATE_KEYED else None
        creds.append({**c.model_dump(), "state": st})
    license_codes = sorted({f"{c['key']}:{c['state']}" if c["state"] else c["key"]
                            for c in creds if c["status"] == "active" and c["key"] != "OTHER"})

    state = state_code(p.state)
    metro = CITY_TO_METRO.get(((p.city or "").strip().lower(), state), "Other")
    years = years_from_dates(p, today)
    software = norm_software(p.software)
    sectors = norm_sectors(p.sectors)

    issues = list(scr.issues)
    wq = p.writing_quality
    if wq.rating == "poor":
        issues.append("poorly_written")
    if "typos" in wq.issues and wq.rating != "good":
        issues.append("typos")
    if "unusual_headings" in wq.issues:
        issues.append("unusual_headers")
    if has_gap(p, today):
        issues.append("career_gap")
    issues = sorted(set(issues))
    if "prompt_injection" in issues:
        quality = "adversarial"
    elif scr.quality == "unusable":
        quality = "unusable"
    elif set(issues) & {"poorly_written", "typos", "unusual_headers", "career_gap", "very_short", "no_dates"}:
        quality = "flawed"
    else:
        quality = "polished"

    profile = {**p.model_dump(), "credentials": creds, "state": state, "metro": metro, "software": software,
               "sectors": sectors, "years_experience": years, "license_codes": license_codes}
    return Validated(profile, license_codes, software, sectors, years, metro, quality, issues, notes)
