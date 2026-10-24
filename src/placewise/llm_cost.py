"""Claude prices and prompt caching, in one place.

Every Claude call logs its cost to `llm_calls`; the daily spend cap and the AI Costs page read it, so the
math must match the bill. Prices: platform.claude.com/docs/en/about-claude/pricing (checked 2026-10-24).

Prompt caching: the shared part of a prompt (tool schema + instructions, and for match scoring the job
order) is marked with `cache_control`. Within 5 minutes, repeats read it from the cache at 5% of the input
price on Sonnet/Opus 5.5 (10% on Haiku 5.5); the first call writes it at 125%. Anthropic only caches
prefixes of 512+ tokens; shorter ones are billed normally (no error).
"""
from langchain_core.messages import SystemMessage

# USD per 1M tokens: (input, output)
PRICES = {
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-opus-5-5": (4.00, 20.00),
}
CACHE_READ = {"claude-sonnet-5-5": 0.05, "claude-opus-5-5": 0.05}   # multiple of the input price; others 0.10
CACHE_WRITE_5M, CACHE_WRITE_1H = 1.25, 2.0


def cached_system(text: str) -> SystemMessage:
    """A system message whose prefix (tool schema + this text) is cached for repeat calls."""
    return SystemMessage(content=[{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}])


def usage_cost(model: str, usage: dict | None) -> dict:
    """Cost of one call from LangChain's usage_metadata.

    LangChain's input_tokens already includes cache reads and writes; split them out and price each.
    Returns {usd, input_tokens, output_tokens, cache_read, cache_write, response_cache}.
    A response replayed from the LangChain response cache (llm_cache.py) costs $0: LangChain marks it
    with total_cost == 0 in usage_metadata.
    """
    u = usage or {}
    if "total_cost" in u and not u["total_cost"]:
        return {"usd": 0.0, "input_tokens": int(u.get("input_tokens") or 0), "output_tokens": int(u.get("output_tokens") or 0),
                "cache_read": 0, "cache_write": 0, "response_cache": True}
    d = u.get("input_token_details") or {}
    total_in, out = int(u.get("input_tokens") or 0), int(u.get("output_tokens") or 0)
    read = int(d.get("cache_read") or 0)
    w1h = int(d.get("ephemeral_1h_input_tokens") or 0)
    w5m = int(d.get("ephemeral_5m_input_tokens") or 0)
    if not (w5m or w1h):                       # older payloads only report cache_creation
        w5m = int(d.get("cache_creation") or 0)
    plain = max(total_in - read - w5m - w1h, 0)
    pin, pout = PRICES.get(model, (0.0, 0.0))
    usd = (plain * pin + read * pin * CACHE_READ.get(model, 0.10)
           + w5m * pin * CACHE_WRITE_5M + w1h * pin * CACHE_WRITE_1H + out * pout) / 1e6
    return {"usd": usd, "input_tokens": total_in, "output_tokens": out, "cache_read": read, "cache_write": w5m + w1h,
            "response_cache": False}
