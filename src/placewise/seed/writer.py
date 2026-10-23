"""Write structured resumes from facts with an LLM (LangChain + Claude Haiku), then fact-check them.

Flow per candidate: prompt → StructuredResume (validated by Pydantic) → structural check
(each job's title, employer and dates match the facts exactly) + text fact check (nothing
missing, no invented credentials) → if problems, retry with them listed (max 2 retries).
Runs concurrently with a cap and tracks tokens and cost.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from . import prompts
from .facts import CandidateFacts
from .factcheck import check
from .catalog import SOFTWARE
from .resume_schema import StructuredResume

ALL_SOFTWARE = {sw for tools in SOFTWARE.values() for sw in tools}

PROMPT_NAME, PROMPT_VERSION = "seed_resume_writer", 5
# USD per 1M tokens for claude-haiku-5-5 (platform.claude.com/docs pricing, checked 2026-10-22)
PRICE_IN, PRICE_OUT = 0.10, 0.50


@dataclass
class WriteResult:
    candidate_id: str
    resume: StructuredResume | None = None
    attempts: int = 0
    problems: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.resume is not None

    @property
    def text(self) -> str | None:
        return self.resume.to_text() if self.resume else None

    @property
    def cost_usd(self) -> float:
        return self.input_tokens / 1e6 * PRICE_IN + self.output_tokens / 1e6 * PRICE_OUT


def facts_for_writer(c: CandidateFacts) -> dict:
    """Only what a resume would contain. No answer-key labels (split, tricky flags, license_codes)."""
    return {
        "name": c.full_name, "email": c.email, "phone": c.phone, "location": f"{c.city}, {c.state}",
        "open_to_relocation": c.open_to_relocation, "discipline": c.discipline.replace("_", " "),
        "specialty": c.subdiscipline,
        "jobs": [{"title": j.title, "employer": j.employer, "location": f"{j.city}, {j.state}",
                  "start": j.start_text, "end": j.end_text,
                  "projects": [{"name": p.name, "sector": p.sector,
                                "value": f"${p.value_usd / 1e6:,.0f}M" if p.value_usd else None}
                               for p in j.projects]} for j in c.jobs],
        "credentials": [cr.text for cr in c.credentials],
        "software": c.software, "sectors": c.sectors,
        "education": [{"degree": e.degree, "school": e.school, "year": str(e.year)} for e in c.education],
    }


def build_messages(c: CandidateFacts, feedback: list[str] | None = None) -> list:
    p = prompts.load(PROMPT_NAME, PROMPT_VERSION)
    h = p["style_hints"]
    user = p["user"].format(
        persona_hint=h["persona"][c.style.persona], length_hint=h["length"][c.style.length],
        header_hint=h["headers"][c.style.header_style], facts_json=json.dumps(facts_for_writer(c), indent=1))
    if feedback:
        user += ("\n\nA previous attempt failed these checks. Fix every one:\n- " + "\n- ".join(feedback[:12]))
    return [SystemMessage(p["system"]), HumanMessage(user)]


def structural_check(r: StructuredResume, c: CandidateFacts) -> list[str]:
    problems = []
    if r.name.strip() != c.full_name:
        problems.append(f"name must be exactly {c.full_name!r}")
    if len(r.jobs) != len(c.jobs):
        problems.append(f"must have exactly {len(c.jobs)} jobs in the same order as the facts (got {len(r.jobs)})")
    for i, (got, want) in enumerate(zip(r.jobs, c.jobs), start=1):
        for fld, expected in (("title", want.title), ("employer", want.employer), ("start", want.start_text),
                              ("end", want.end_text)):
            if getattr(got, fld).strip() != expected:
                problems.append(f"job {i} {fld} must be exactly {expected!r} (got {getattr(got, fld)!r})")
        if not 1 <= len(got.bullets) <= 6:
            problems.append(f"job {i} needs 2-5 bullets (got {len(got.bullets)})")
    # Software must come from the facts: flag any known A/E/C tool that isn't the candidate's
    text = r.to_text()
    for sw in sorted(c.software, key=len, reverse=True):  # scrub allowed names, longest first
        text = re.sub(re.escape(sw), " ", text, flags=re.I)
    for sw in sorted(ALL_SOFTWARE - set(c.software), key=len, reverse=True):
        # "Revit" is fine when the facts list "Revit MEP": same product family
        if any(have.lower().startswith(sw.lower() + " ") for have in c.software):
            continue
        if re.search(rf"(?<![\w-]){re.escape(sw)}(?![\w-])", text, flags=re.I):
            problems.append(f"software not in facts: {sw!r} (only use the facts' software list)")
    # Only flag claims about the PERSON relocating; "utility relocation" is normal civil work
    if not c.open_to_relocation and re.search(r"(open|willing|available)\s+(to|for)\s+relocat|relocat\w*\s*:",
                                              " ".join(r.contact) + " " + r.summary, re.I):
        problems.append("do not mention relocation: the candidate is not open to relocation")
    want_edu = sorted((e.degree, e.school, str(e.year)) for e in c.education)
    got_edu = sorted((e.degree.strip(), e.school.strip(), e.year.strip()) for e in r.education)
    if got_edu != want_edu:
        problems.append(f"education must be exactly {want_edu}")
    want_creds = [cr.text for cr in c.credentials]
    if sorted(x.strip() for x in r.credentials) != sorted(want_creds):
        problems.append(f"credentials must be exactly {want_creds}")
    return problems


async def write_one(model, c: CandidateFacts, sem: asyncio.Semaphore, max_retries: int = 2) -> WriteResult:
    res = WriteResult(candidate_id=c.candidate_id)
    feedback: list[str] | None = None
    t0 = time.perf_counter()
    async with sem:
        for attempt in range(1, max_retries + 2):
            res.attempts = attempt
            try:
                out = await model.ainvoke(build_messages(c, feedback))
            except Exception as e:
                res.problems = [f"api error: {type(e).__name__}: {e}"]
                status = getattr(e, "status_code", None)
                if status is not None and 400 <= status < 500 and status != 429:
                    break  # permanent request error; retrying can't fix it
                await asyncio.sleep(min(2 ** attempt, 10))
                continue
            u = getattr(out["raw"], "usage_metadata", None) or {}
            res.input_tokens += u.get("input_tokens", 0)
            res.output_tokens += u.get("output_tokens", 0)
            resume: StructuredResume | None = out["parsed"]
            if resume is None:
                feedback = [f"output did not match the schema: {out.get('parsing_error')}"]
                res.problems = feedback
                continue
            problems = structural_check(resume, c) + check(resume.to_text(), c)
            if not problems:
                res.resume, res.problems = resume, []
                break
            res.problems = feedback = problems
    res.seconds = round(time.perf_counter() - t0, 2)
    return res


def make_model():
    model_id = prompts.load(PROMPT_NAME, PROMPT_VERSION)["model"]
    # No `temperature`: Claude 5.5 models reject it. Variety comes from persona/length/header hints.
    llm = ChatAnthropic(model=model_id, max_tokens=4000, max_retries=4, timeout=120)
    return llm.with_structured_output(StructuredResume, include_raw=True)


async def write_many(cands: list[CandidateFacts], concurrency: int = 8, on_done=None) -> list[WriteResult]:
    model = make_model()
    sem = asyncio.Semaphore(concurrency)

    async def run(c):
        r = await write_one(model, c, sem)
        if on_done:
            on_done(r)
        return r

    return await asyncio.gather(*(run(c) for c in cands))
