"""Retrieval eval: do the known strong candidates for each job order come back near the top?

    docker compose run --rm --entrypoint python seed -m placewise.evals.retrieval

Query = the job order's title + requirements in plain words. Relevant = candidates graded 'strong' in
the answer key (mapped to app person ids). Compares vector / keyword / hybrid / hybrid+rerank, each
without and with hard filters derived from the job order. Metrics are per person: recall@10, recall@20,
precision@10 (strong or partial counted as relevant), MRR (rank of the first strong match).
"""
import asyncio
import collections
import json
import statistics

import psycopg

from placewise.config import get_settings
from placewise.db import close_pool, open_pool
from placewise.rag.rerank import rerank
from placewise.rag.retrieve import Filters, group_by_candidate, hybrid
from placewise.seed.job_orders import SPECS
from placewise.seed.paths import TRUTH


def spec_query(jo) -> str:
    return jo.title + ". " + "; ".join(r.text for r in jo.must_have + jo.nice_to_have if r.text)


def spec_filters(jo) -> Filters:
    f = Filters()
    for r in jo.must_have:
        if r.kind == "discipline":
            f.discipline = r.value
        elif r.kind == "metro":
            f.metro = r.value
        elif r.kind == "years":
            f.min_years = float(r.value)
        elif r.kind in ("license", "cert") and not r.accept and (r.state or r.value not in ("PE", "EIT", "RA", "SE")):
            f.license_codes.append(f"{r.value}:{r.state}" if r.state else r.value)
    return f


async def run() -> None:
    await open_pool()
    with psycopg.connect(get_settings().database_url) as conn:
        cid_to_person = {ref: pid for ref, pid in conn.execute(
            "SELECT source_ref, person_id FROM resume_files WHERE source = 'seed' AND person_id IS NOT NULL")}
    strong, relevant = collections.defaultdict(set), collections.defaultdict(set)
    for row in map(json.loads, (TRUTH / "relevance.jsonl").open()):
        pid = cid_to_person.get(row["candidate_id"])
        if pid is None:
            continue
        if row["grade"] == "strong":
            strong[row["job_order_id"]].add(pid)
        if row["grade"] in ("strong", "partial"):
            relevant[row["job_order_id"]].add(pid)

    results = collections.defaultdict(list)
    for jo in SPECS:
        if not strong[jo.job_order_id]:
            continue
        q = spec_query(jo)
        for filt_name, f in (("no filters", Filters()), ("with filters", spec_filters(jo))):
            for mode in ("vector", "keyword", "hybrid", "hybrid+rerank"):
                hits = await hybrid(q, f, k=60, mode="hybrid" if mode == "hybrid+rerank" else mode)
                if mode == "hybrid+rerank":
                    hits = await rerank(q, hits[:60], top_k=40)
                    ranked = [g.person_id for g in group_by_candidate(hits, "rerank")]
                else:
                    ranked = [g.person_id for g in group_by_candidate(hits, "rrf")]
                s, rel = strong[jo.job_order_id], relevant[jo.job_order_id]
                first = next((i + 1 for i, p in enumerate(ranked) if p in s), None)
                results[(filt_name, mode)].append({
                    "jo": jo.job_order_id,
                    "r10": len(set(ranked[:10]) & s) / min(len(s), 10),
                    "r20": len(set(ranked[:20]) & s) / min(len(s), 20),
                    "p10": len(set(ranked[:10]) & rel) / max(min(len(ranked), 10), 1),
                    "mrr": 1 / first if first else 0.0,
                })
    await close_pool()
    n = len(results[("no filters", "vector")])
    print(f"job orders evaluated: {n} (JO-15 excluded: no strong match by design)\n")
    print(f"{'filters':<13} {'mode':<15} {'recall@10':>9} {'recall@20':>9} {'prec@10':>8} {'MRR':>6}")
    for (fn, mode), rows in results.items():
        m = lambda k: statistics.mean(r[k] for r in rows)  # noqa: E731
        print(f"{fn:<13} {mode:<15} {m('r10'):>9.1%} {m('r20'):>9.1%} {m('p10'):>8.1%} {m('mrr'):>6.2f}")
    json.dump({f"{k[0]}|{k[1]}": v for k, v in results.items()},
              open("/app/outputs/evals/retrieval.json", "w"), indent=1)


if __name__ == "__main__":
    asyncio.run(run())
