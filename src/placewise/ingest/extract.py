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

from ..llm_cost import cached_system, usage_cost
from ..promptlib import load
from .schema import ExtractedProfile

PROMPT_NAME, PROMPT_VERSION = "ingest_extract_profile", 1


@dataclass
class Extraction:
    profile: ExtractedProfile | None
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    attempts: int = 0
    problems: list[str] = field(default_factory=list)
    cost_usd: float = 0.0
    cached_tokens: int = 0


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
    # Tool schema + instructions are the same for every resume: cached across a batch of uploads.
    messages = [cached_system(p["system"]), HumanMessage(p["user"].format(resume_text=resume_text[:30000]))]
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
        c = usage_cost(model_id, getattr(out["raw"], "usage_metadata", None))
        res.input_tokens += c["input_tokens"]
        res.output_tokens += c["output_tokens"]
        res.cached_tokens += c["cache_read"]
        res.cost_usd += c["usd"]
        if out.get("parsed") is not None:
            res.profile = out["parsed"]
            res.problems = []
            break
        res.problems = [f"schema: {out.get('parsing_error')}"]
    res.latency_ms = int((time.perf_counter() - t0) * 1000)
    return res
