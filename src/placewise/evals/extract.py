"""Evaluate profile extraction (parse → screen → LLM extract → code validate) against the answer key.

    docker compose run --rm --entrypoint python seed -m placewise.evals.extract --model claude-haiku-5-5 --limit 20

Dev split by default (the test split is reserved for the final eval). Writes a JSON report to
outputs/evals/. Every LLM call is traced in LangSmith with tags [eval, extract, <model>].
"""
import argparse
import asyncio
import json
import os
import statistics
import time
from datetime import date
from pathlib import Path

from placewise.ingest.extract import extract
from placewise.ingest.parse import parse
from placewise.ingest.screen import screen
from placewise.ingest.sources import seed_original
from placewise.ingest.validate import validate
from placewise.seed.facts import AS_OF, CandidateFacts
from placewise.seed.paths import TRUTH

FLAWS = {"typos", "poorly_written", "unusual_headers", "career_gap"}


async def run_one(c: CandidateFacts, model: str, sem: asyncio.Semaphore) -> dict:
    async with sem:
        p = parse(seed_original(c.candidate_id).read_bytes())
        s = screen(p)
        row = {"id": c.candidate_id, "truth_quality": c.quality}
        if s.quality == "unusable":
            return {**row, "skipped": "unusable", "detected_quality": "unusable"}
        ex = await extract(s.clean_text, model_id=model, run_name=f"eval_extract:{c.candidate_id}",
                           tags=["eval", "extract"])
        row |= {"cost": ex.cost_usd, "latency_ms": ex.latency_ms, "attempts": ex.attempts}
        if ex.profile is None:
            return {**row, "error": ex.problems}
        v = validate(ex.profile, s.clean_text, s, today=AS_OF)
        tl, pl = set(c.license_codes), set(v.license_codes)
        row |= {
            "license_exact": tl == pl, "license_tp": len(tl & pl), "license_fp": len(pl - tl), "license_fn": len(tl - pl),
            "license_truth": sorted(tl), "license_pred": sorted(pl),
            "years_err": None if v.years_experience is None else abs(v.years_experience - c.years_experience),
            "metro_ok": v.metro == c.metro, "discipline_ok": ex.profile.discipline == c.discipline,
            "sw_tp": len(set(c.software) & set(v.software)), "sw_fp": len(set(v.software) - set(c.software)),
            "sw_fn": len(set(c.software) - set(v.software)),
            "detected_quality": v.quality, "detected_issues": v.quality_issues, "truth_issues": c.quality_issues,
            "dropped": v.notes,
        }
        return row


def pr(tp, fp, fn):
    return (tp / (tp + fp) if tp + fp else 1.0), (tp / (tp + fn) if tp + fn else 1.0)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-sonnet-5-5")
    ap.add_argument("--split", default="dev")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--concurrency", type=int, default=8)
    a = ap.parse_args()
    cands = [CandidateFacts.model_validate(json.loads(l)) for l in (TRUTH / "candidates.jsonl").open()]
    cands = [c for c in cands if c.split == a.split]
    if a.limit:
        cands = cands[: a.limit]
    t0 = time.perf_counter()
    sem = asyncio.Semaphore(a.concurrency)
    rows = await asyncio.gather(*(run_one(c, a.model, sem) for c in cands))
    secs = time.perf_counter() - t0
    ok = [r for r in rows if "license_exact" in r]
    tp, fp, fn = (sum(r[k] for r in ok) for k in ("license_tp", "license_fp", "license_fn"))
    lp, lr = pr(tp, fp, fn)
    stp, sfp, sfn = (sum(r[k] for r in ok) for k in ("sw_tp", "sw_fp", "sw_fn"))
    sp, sr = pr(stp, sfp, sfn)
    yerr = [r["years_err"] for r in ok if r["years_err"] is not None]
    fl_tp = sum(1 for r in ok if r["truth_quality"] == "flawed" and r["detected_quality"] == "flawed")
    fl_fp = sum(1 for r in ok if r["truth_quality"] != "flawed" and r["detected_quality"] == "flawed")
    fl_fn = sum(1 for r in ok if r["truth_quality"] == "flawed" and r["detected_quality"] != "flawed")
    fp_, fr_ = pr(fl_tp, fl_fp, fl_fn)
    adv = [r for r in rows if r["truth_quality"] == "adversarial"]
    report = {
        "model": a.model, "split": a.split, "n": len(rows), "extracted": len(ok),
        "errors": [r for r in rows if "error" in r],
        "license_exact_match": sum(r["license_exact"] for r in ok) / max(len(ok), 1),
        "license_precision": lp, "license_recall": lr,
        "years_mae": statistics.mean(yerr) if yerr else None,
        "years_within_1": sum(1 for e in yerr if e <= 1) / max(len(yerr), 1),
        "metro_accuracy": sum(r["metro_ok"] for r in ok) / max(len(ok), 1),
        "discipline_accuracy": sum(r["discipline_ok"] for r in ok) / max(len(ok), 1),
        "software_precision": sp, "software_recall": sr,
        "flawed_precision": fp_, "flawed_recall": fr_, "flawed_tp_fp_fn": [fl_tp, fl_fp, fl_fn],
        "adversarial_flagged": f"{sum(1 for r in adv if r['detected_quality'] == 'adversarial')}/{len(adv)}",
        "cost_usd": sum(r.get("cost", 0) for r in rows),
        "cost_per_resume": sum(r.get("cost", 0) for r in rows) / max(len(ok), 1),
        "latency_p50_ms": statistics.median([r["latency_ms"] for r in ok]) if ok else None,
        "wall_seconds": round(secs, 1),
        "license_misses": [{"id": r["id"], "truth": r["license_truth"], "pred": r["license_pred"]}
                           for r in ok if not r["license_exact"]][:15],
    }
    out = Path("/app/outputs/evals")
    out.mkdir(parents=True, exist_ok=True)
    stamp = f"extract_{a.model}_{a.split}_{len(rows)}"
    (out / f"{stamp}.json").write_text(json.dumps({"summary": report, "rows": rows}, indent=1, default=str))
    for k, v in report.items():
        if k not in ("errors", "license_misses"):
            print(f"{k:<22} {v:.3f}" if isinstance(v, float) else f"{k:<22} {v}")
    print("errors:", len(report["errors"]))
    for m in report["license_misses"]:
        print("  license miss", m)


if __name__ == "__main__":
    os.environ.setdefault("LANGSMITH_PROJECT", "placewise")
    asyncio.run(main())
