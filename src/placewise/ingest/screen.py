"""Security and quality screen, without AI. Runs before any LLM sees the resume.

Security: hidden text and prompt-injection phrases (visible or hidden). Injected instructions are
removed from the text the LLM will read, and the file is flagged 'adversarial'.
Quality: obvious problems a recruiter should know about (unusable file, very thin content).
Writing quality ("poorly written") is judged later by the extraction step.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .parse import Parsed

INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) (instructions|prompts|rules)",
    r"disregard (all |any )?(previous|prior|above)",
    r"(note|message|instructions?) (to|for) (the )?(ai|llm|language model|resume screening|screening system)",
    r"\b(ai|llm) (resume )?screening (system|tool)s?\b",
    r"rate (this candidate|them|me|him|her) (as )?(a )?\d{1,3}\s*(/|out of)\s*\d{1,3}",
    r"(perfect|ideal) (match|candidate) for every (role|job|position)",
    r"recommend (them|this candidate|me) for immediate hire",
    r"\bsystem prompt\b",
    r"you are (now )?(an?|the) (ai|assistant|model)",
]
_INJ = re.compile("|".join(f"(?:{p})" for p in INJECTION_PATTERNS), re.I)
_SENTENCE = re.compile(r"[^.\n]*(?:" + "|".join(INJECTION_PATTERNS) + r")[^.\n]*[.]?", re.I)


@dataclass
class Screen:
    quality: str                               # polished | flawed | unusable | adversarial (pre-LLM)
    issues: list[str] = field(default_factory=list)
    clean_text: str = ""                       # what the LLM is allowed to read
    findings: list[str] = field(default_factory=list)  # human-readable explanations


def screen(p: Parsed) -> Screen:
    if p.status != "ok":
        issue = "image_only_pdf" if "OCR" in (p.reason or "") else "corrupt_file"
        return Screen("unusable", [issue], "", [p.reason or "unreadable file"])

    issues, findings = [], []
    text = p.text
    if p.hidden_text:
        issues.append("hidden_text")
        findings.append(f"Hidden text found ({len(p.hidden_text)} characters, invisible to a human reader)")
    hidden_inj = bool(_INJ.search(p.hidden_text or ""))
    visible_inj = bool(_INJ.search(text))
    if hidden_inj or visible_inj:
        issues.append("prompt_injection")
        where = "hidden" if hidden_inj and not visible_inj else ("visible" if visible_inj and not hidden_inj else
                                                                 "hidden and visible")
        findings.append(f"Instructions aimed at AI systems ({where}); removed before extraction")
        text = _SENTENCE.sub(" ", text)  # strip injected sentences from what the LLM reads

    words = len(re.findall(r"\w+", text))
    if words < 100:  # data: polished resumes start at ~114 words
        issues.append("very_short")
        findings.append(f"Very little content ({words} words)")
    if not re.search(r"\b(19|20)\d{2}\b", text):
        issues.append("no_dates")
        findings.append("No dates found: work history can't be verified")

    if "prompt_injection" in issues:
        quality = "adversarial"
    elif issues:
        quality = "flawed"
    else:
        quality = "polished"
    return Screen(quality, issues, text.strip(), findings)
