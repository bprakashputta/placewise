"""LLM extraction of a structured profile (LangChain + Claude, structured output).

The model is configurable so the eval can compare Sonnet and Haiku on the same resumes.
Returns the parsed profile plus token usage; never raises on bad model output (returns problems).
"""
from __future__ import annotations

import time
import warnings
from dataclasses import dataclass, field

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from ..promptlib import load
from .schema import ExtractedProfile

PROMPT_NAME, PROMPT_VERSION = "ingest_extract_profile", 1
# USD per 1M tokens (input, output), platform.claude.com/docs pricing, checked 2026-10-22
PRICES = {"claude-sonnet-5-5": (2.00, 10.00), "claude-haiku-5-5": (0.10, 0.50), "claude-opus-5-5": (4.00, 20.00)}


@dataclass
class Extraction:
    profile: ExtractedProfile | None
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    attempts: int = 0
    problems: list[str] = field(default_factory=list)

    @property
    def cost_usd(self) -> float:
        pin, pout = PRICES.get(self.model, (0, 0))
        return self.input_tokens / 1e6 * pin + self.output_tokens / 1e6 * pout


_models: dict[str, object] = {}


def _model(model_id: str):
    if model_id not in _models:
        llm = ChatAnthropic(model=model_id, max_tokens=6000, max_retries=4, timeout=120)
        # Tool-calling structured output. Tried method="json_schema" (LangChain's suggestion for 5.5
        # models): the API rejected ExtractedProfile with 400 "Schema is too complex". Tool calling scored
        # 100% on licenses over 167 dev resumes, and a missing tool call is handled below as a retry.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            _models[model_id] = llm.with_structured_output(ExtractedProfile, include_raw=True)
    return _models[model_id]


async def extract(resume_text: str, model_id: str | None = None, run_name: str = "extract_profile",
                  tags: list[str] | None = None, max_attempts: int = 2) -> Extraction:
    p = load(PROMPT_NAME, PROMPT_VERSION)
    model_id = model_id or p["model"]
    res = Extraction(profile=None, model=model_id)
    messages = [SystemMessage(p["system"]), HumanMessage(p["user"].format(resume_text=resume_text[:30000]))]
    t0 = time.perf_counter()
    for attempt in range(1, max_attempts + 1):
        res.attempts = attempt
        try:
            out = await _model(model_id).ainvoke(
                messages, config={"run_name": run_name, "tags": [*(tags or []), f"prompt:v{PROMPT_VERSION}", model_id],
                                  "metadata": {"prompt": PROMPT_NAME, "prompt_version": PROMPT_VERSION}})
        except Exception as e:  # never crash the caller: report, and retry only if it may be transient
            res.problems = [f"api error: {type(e).__name__}: {str(e)[:300]}"]
            status = getattr(e, "status_code", None)
            if status is not None and 400 <= status < 500 and status != 429:
                break
            continue
        u = getattr(out["raw"], "usage_metadata", None) or {}
        res.input_tokens += u.get("input_tokens", 0)
        res.output_tokens += u.get("output_tokens", 0)
        if out.get("parsed") is not None:
            res.profile = out["parsed"]
            res.problems = []
            break
        res.problems = [f"schema: {out.get('parsing_error')}"]
    res.latency_ms = int((time.perf_counter() - t0) * 1000)
    return res
