"""One wrapper for every LLM call. It does three jobs:
1. Structured output: the model must return JSON that validates against a Pydantic schema.
   If validation fails, the error is sent back to the model and it retries (bounded).
2. Logging: every attempt is written to llm_calls with tokens, latency, cost and status.
3. Provider switch: Anthropic or OpenAI behind the same interface.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, ValidationError

from .config import PRICES_PER_MTOK, get_settings
from .db import get_conn

T = TypeVar("T", bound=BaseModel)

_clients: dict[str, Any] = {}


def new_run_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _client(provider: str):
    if provider not in _clients:
        s = get_settings()
        if provider == "anthropic":
            import anthropic
            _clients[provider] = anthropic.Anthropic(api_key=s.anthropic_api_key, timeout=s.llm_timeout_s, max_retries=2)
        else:
            import openai
            _clients[provider] = openai.OpenAI(api_key=s.openai_api_key, timeout=s.llm_timeout_s, max_retries=2)
    return _clients[provider]


def _cost(model: str, inp: int, out: int) -> float | None:
    p = PRICES_PER_MTOK.get(model)
    return None if not p else round(inp / 1e6 * p[0] + out / 1e6 * p[1], 6)


def log_call(*, run_id, step, provider, model, prompt_version, inp=0, out=0, cached=0,
             latency_ms=0, attempt=1, status="ok", error=None) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO llm_calls (run_id, step, provider, model, prompt_version, input_tokens,
               output_tokens, cached_tokens, latency_ms, cost_usd, attempt, status, error)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (run_id, step, provider, model, prompt_version, inp, out, cached, latency_ms,
             _cost(model, inp, out), attempt, status, (error or "")[:2000] or None),
        )


def complete_structured(
    *,
    schema: type[T],
    system: str,
    user: str,
    step: str,
    run_id: str,
    prompt_version: str,
    tier: str = "fast",
    max_tokens: int = 4000,
) -> T:
    """Call the model and return a validated `schema` instance, or raise after retries."""
    s = get_settings()
    provider, model = s.provider, s.model(tier)
    json_schema = schema.model_json_schema()
    messages: list[dict] = [{"role": "user", "content": user}]
    last_err: str | None = None

    for attempt in range(1, s.llm_max_retries + 2):
        t0 = time.perf_counter()
        inp = out = cached = 0
        raw: Any = None
        try:
            if provider == "anthropic":
                resp = _client(provider).messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    # The system prompt is the same on every call for a step, so mark it cacheable.
                    system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                    messages=messages,
                    tools=[{"name": "submit", "description": f"Submit the {schema.__name__}", "input_schema": json_schema}],
                    tool_choice={"type": "tool", "name": "submit"},
                )
                u = resp.usage
                inp, out = u.input_tokens, u.output_tokens
                cached = (getattr(u, "cache_read_input_tokens", 0) or 0)
                block = next(b for b in resp.content if b.type == "tool_use")
                raw = block.input
            else:
                resp = _client(provider).chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": system}, *messages],
                    response_format={"type": "json_schema",
                                     "json_schema": {"name": schema.__name__, "schema": json_schema, "strict": False}},
                )
                u = resp.usage
                inp, out = u.prompt_tokens, u.completion_tokens
                cached = getattr(getattr(u, "prompt_tokens_details", None), "cached_tokens", 0) or 0
                raw = json.loads(resp.choices[0].message.content)

            result = schema.model_validate(raw)
            log_call(run_id=run_id, step=step, provider=provider, model=model, prompt_version=prompt_version,
                     inp=inp, out=out, cached=cached, latency_ms=int((time.perf_counter() - t0) * 1000), attempt=attempt)
            return result

        except ValidationError as e:
            last_err = str(e)
            log_call(run_id=run_id, step=step, provider=provider, model=model, prompt_version=prompt_version,
                     inp=inp, out=out, cached=cached, latency_ms=int((time.perf_counter() - t0) * 1000),
                     attempt=attempt, status="invalid_output", error=last_err)
            # Feed the validation error back so the model can fix its own output.
            messages = [
                {"role": "user", "content": user},
                {"role": "assistant", "content": json.dumps(raw)[:6000] if raw is not None else "(no output)"},
                {"role": "user", "content": f"Your output failed validation:\n{last_err[:1500]}\nReturn corrected output."},
            ]
        except Exception as e:  # network, rate limit after SDK retries, etc.
            last_err = f"{type(e).__name__}: {e}"
            log_call(run_id=run_id, step=step, provider=provider, model=model, prompt_version=prompt_version,
                     latency_ms=int((time.perf_counter() - t0) * 1000), attempt=attempt, status="error", error=last_err)
            time.sleep(min(2 ** attempt, 8))

    raise RuntimeError(f"{step} failed after {s.llm_max_retries + 1} attempts: {last_err}")


# ---------------------------------------------------------------- agent tool loop

def run_tool_loop(
    *,
    system: str,
    user: str,
    tools: list[dict],
    handlers: dict[str, Callable[..., Any]],
    run_id: str,
    prompt_version: str,
    on_event: Callable[[dict], None] | None = None,
) -> dict:
    """Minimal agent loop: model picks a tool, we run it, feed the result back, repeat.
    Stops on a final answer, max steps, or the token budget."""
    s = get_settings()
    provider, model = s.provider, s.model("smart")
    trace: list[dict] = []
    total_tokens = 0
    emit = on_event or (lambda e: None)

    if provider == "anthropic":
        messages: list[dict] = [{"role": "user", "content": user}]
        for step in range(1, s.agent_max_steps + 1):
            t0 = time.perf_counter()
            resp = _client(provider).messages.create(
                model=model, max_tokens=2000,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=messages, tools=tools,
            )
            u = resp.usage
            total_tokens += u.input_tokens + u.output_tokens
            log_call(run_id=run_id, step=f"agent.step{step}", provider=provider, model=model,
                     prompt_version=prompt_version, inp=u.input_tokens, out=u.output_tokens,
                     cached=getattr(u, "cache_read_input_tokens", 0) or 0,
                     latency_ms=int((time.perf_counter() - t0) * 1000))
            messages.append({"role": "assistant", "content": [
                {"type": "text", "text": b.text} if b.type == "text"
                else {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
                for b in resp.content if b.type in ("text", "tool_use")
            ]})
            tool_uses = [b for b in resp.content if b.type == "tool_use"]
            if not tool_uses:
                text = "".join(b.text for b in resp.content if b.type == "text")
                return {"answer": text, "trace": trace, "steps": step, "tokens": total_tokens}
            results = []
            for tu in tool_uses:
                out = _run_tool(tu.name, tu.input, handlers)
                trace.append({"step": step, "tool": tu.name, "input": tu.input, "output_preview": str(out)[:400]})
                emit(trace[-1])
                results.append({"type": "tool_result", "tool_use_id": tu.id, "content": json.dumps(out, default=str)[:12000]})
            messages.append({"role": "user", "content": results})
            if total_tokens > s.agent_max_tokens_total:
                return {"answer": "Stopped: token budget reached. Partial trace attached.", "trace": trace,
                        "steps": step, "tokens": total_tokens}
    else:
        oa_tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                       "parameters": t["input_schema"]}} for t in tools]
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        for step in range(1, s.agent_max_steps + 1):
            t0 = time.perf_counter()
            resp = _client(provider).chat.completions.create(model=model, messages=messages, tools=oa_tools)
            u = resp.usage
            total_tokens += u.prompt_tokens + u.completion_tokens
            log_call(run_id=run_id, step=f"agent.step{step}", provider=provider, model=model,
                     prompt_version=prompt_version, inp=u.prompt_tokens, out=u.completion_tokens,
                     latency_ms=int((time.perf_counter() - t0) * 1000))
            msg = resp.choices[0].message
            messages.append(msg.model_dump(exclude_none=True))
            if not msg.tool_calls:
                return {"answer": msg.content or "", "trace": trace, "steps": step, "tokens": total_tokens}
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                out = _run_tool(tc.function.name, args, handlers)
                trace.append({"step": step, "tool": tc.function.name, "input": args, "output_preview": str(out)[:400]})
                emit(trace[-1])
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(out, default=str)[:12000]})
            if total_tokens > s.agent_max_tokens_total:
                return {"answer": "Stopped: token budget reached. Partial trace attached.", "trace": trace,
                        "steps": step, "tokens": total_tokens}

    return {"answer": "Stopped: max steps reached. Partial trace attached.", "trace": trace,
            "steps": s.agent_max_steps, "tokens": total_tokens}


def _run_tool(name: str, args: dict, handlers: dict[str, Callable[..., Any]]) -> Any:
    fn = handlers.get(name)
    if fn is None:
        return {"error": f"unknown tool {name}"}
    try:
        return fn(**args)
    except Exception as e:  # tool errors go back to the model as data, not as a crash
        return {"error": f"{type(e).__name__}: {e}"}
