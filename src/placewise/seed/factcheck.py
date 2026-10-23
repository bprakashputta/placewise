"""Verify a generated resume against its facts.

Two directions:
- Missing: every must-include string (name, credentials, employers, dates, school) appears.
- Invented: no credential is mentioned that the facts don't contain.
If either fails, the resume is rewritten (with the problems fed back) or rejected, so the
answer key always matches what the resume actually says.
"""
import re

from .facts import CandidateFacts

# Credential mentions to watch for when they are NOT in the facts.
CRED_PATTERNS = {
    "PE": r"\bP\.?\s?E\.?\b(?!\w)|Professional Engineer",
    "EIT": r"\bE\.?I\.?T\.?\b|Engineer[- ]in[- ]Training",
    "RA": r"Registered Architect|Licensed Architect",
    "SE": r"\bS\.E\.,|Structural Engineer \(SE\)",
    "NCARB": r"\bNCARB\b",
    "NCIDQ": r"\bNCIDQ\b",
    "TX_RID": r"Registered Interior Designer",
    "LEED": r"\bLEED\b",
    "PMP": r"\bPMP\b|Project Management Professional",
    "CCM": r"\bCCM\b|Certified Construction Manager",
    "OSHA": r"\bOSHA\b",
}


def must_include(c: CandidateFacts) -> list[str]:
    items = [c.full_name]
    items += [cr.text for cr in c.credentials]
    for j in c.jobs:
        items += [j.employer, j.title, j.start_text, j.end_text]
    items += [e.school for e in c.education]
    return list(dict.fromkeys(i for i in items if i))


def _norm(s: str) -> str:
    s = s.replace("–", "-").replace("—", "-").replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip().lower()


def check(text: str, c: CandidateFacts) -> list[str]:
    problems: list[str] = []
    norm = _norm(text)
    for item in must_include(c):
        if _norm(item) not in norm:
            problems.append(f"missing exact text: {item!r}")

    # Remove allowed mentions (credential phrases, job titles), then look for leftovers.
    # Titles are removed because e.g. "Civil Engineer in Training" contains "Engineer in Training".
    scrubbed = text
    for allowed in [cr.text for cr in c.credentials] + [j.title for j in c.jobs]:
        scrubbed = re.sub(re.escape(allowed), " ", scrubbed, flags=re.I)
    # Only credentials actually HELD exempt their family. Someone "pursuing PE" must not be
    # described as a PE anywhere beyond their exact allowed phrase.
    held_families = {"LEED" if cr.key.startswith("LEED") else ("OSHA" if cr.key == "OSHA_30" else cr.key)
                     for cr in c.credentials if cr.counts}
    for fam, pat in CRED_PATTERNS.items():
        if fam in held_families:
            continue
        m = re.search(pat, scrubbed)
        if m:
            problems.append(f"invented credential not in facts: {m.group(0)!r} ({fam})")
    # Family exemptions are too coarse for the traps that matter: check the exact level/state.
    held = [cr for cr in c.credentials if cr.counts]
    if any(cr.key == "LEED_GA" for cr in held) and not any(cr.key == "LEED_AP" for cr in held):
        if re.search(r"LEED\s+AP|LEED Accredited Professional", scrubbed, flags=re.I):
            problems.append("claims LEED AP but the facts only have LEED Green Associate")
    state_names = {"TX": "Texas", "OK": "Oklahoma", "LA": "Louisiana", "AR": "Arkansas", "CO": "Colorado",
                   "NM": "New Mexico", "AZ": "Arizona", "GA": "Georgia", "IL": "Illinois"}
    for key, words in (("PE", r"(?:\bP\.?E\.?\b|Professional Engineer)"), ("RA", r"(?:Registered|Licensed) Architect")):
        held_states = {cr.state for cr in held if cr.key == key}
        for st, name in state_names.items():
            if st in held_states:
                continue
            if re.search(rf"(?:{name}|\b{st}\b)[^.\n]{{0,25}}{words}|{words}[^.\n]{{0,25}}(?:{name}|\b{st}\b)",
                         scrubbed, flags=re.I if key == "RA" else 0):
                problems.append(f"implies a {key} in {name}, which the facts don't have")
                break
    if re.search(r"```|^(here is|sure,|certainly)", text.strip(), flags=re.I):
        problems.append("contains commentary or code fences")
    return problems
