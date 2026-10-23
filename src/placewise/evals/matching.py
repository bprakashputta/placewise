"""Matching eval: run a match for every seed job order and grade the shortlist against the answer key.

    docker compose run --rm --entrypoint python seed -m placewise.evals.matching

Reports per job order and overall: precision@5 (strong, and strong-or-partial), 'submit' precision,
near misses wrongly recommended, JO-15 (unfillable) behavior, filter relaxations, and cost.
"""
import asyncio
import collections
import json

import psycopg

from placewise.config import get_settings
from placewise.db import close_pool, open_pool
from placewise.matching import engine
from placewise.seed.facts import CandidateFacts
from placewise.seed.paths import TRUTH


async def main() -> None:
    import sys
    regrade_only = "--regrade" in sys.argv   # re-score the latest runs from stored verdicts (no LLM calls)
    await open_pool()
    url = get_settings().database_url
    with psycopg.connect(url) as conn:
        jobs = conn.execute("SELECT id, source_ref FROM job_orders WHERE source_ref IS NOT NULL ORDER BY id").fetchall()
        cid_to_pid = dict(conn.execute("SELECT source_ref, person_id FROM resume_files "
                                       "WHERE source='seed' AND person_id IS NOT NULL").fetchall())
    grade = collections.defaultdict(dict)
    for row in map(json.loads, (TRUTH / "relevance.jsonl").open()):
        pid = cid_to_pid.get(row["candidate_id"])
        if pid:
            g = grade[row["job_order_id"]]
            order = {"strong": 2, "partial": 1, "none": 0}
            g[pid] = max(g.get(pid, "none"), row["grade"], key=order.get)
    near = collections.defaultdict(set)
    for c in (CandidateFacts.model_validate(json.loads(l)) for l in (TRUTH / "candidates.jsonl").open()):
        if c.targets_job_order and "near_miss" in c.targets_job_order and c.candidate_id in cid_to_pid:
            near[c.targets_job_order.split(":")[0]].add(cid_to_pid[c.candidate_id])

    runs = {}
    if regrade_only:
        from placewise.matching.schema import JobSpec, RequirementVerdict
        with psycopg.connect(url) as conn:
            for jid, ref in jobs:
                spec = JobSpec.model_validate(conn.execute("SELECT spec FROM job_orders WHERE id=%s",
                                                           (jid,)).fetchone()[0])
                runs[ref] = conn.execute("SELECT run_id FROM match_runs WHERE job_order_id=%s AND status='done' "
                                         "ORDER BY started_at DESC LIMIT 1", (jid,)).fetchone()[0]
                for mid, verdicts in conn.execute("SELECT id, verdicts FROM matches WHERE run_id=%s", (runs[ref],)):
                    sc, rec = engine.score(spec, [RequirementVerdict.model_validate(v) for v in verdicts])
                    conn.execute("UPDATE matches SET score=%s, recommendation=%s WHERE id=%s", (sc, rec, mid))
            conn.commit()
    else:
        for jid, ref in jobs:   # one job order at a time: stay well inside the API rate limit
            runs[ref] = await engine.run_match(jid)
            await asyncio.gather(*list(engine._tasks))
    await close_pool()

    tot = collections.Counter()
    print(f"{'job':<6} {'top5 strong':>11} {'top5 rel':>9} {'submit':>7} {'submit ok':>9} {'near→submit':>11} "
          f"{'relaxed':<14} cost")
    with psycopg.connect(url) as conn:
        for jid, ref in jobs:
            run = conn.execute("SELECT status, relaxed, cost_usd, error FROM match_runs WHERE run_id=%s",
                               (runs[ref],)).fetchone()
            ms = conn.execute("SELECT person_id, score, recommendation FROM matches WHERE run_id=%s "
                              "ORDER BY score DESC, retrieval_rank", (runs[ref],)).fetchall()
            g = grade[ref]
            top5 = [m[0] for m in ms[:5]]
            s5 = sum(g.get(p) == "strong" for p in top5)
            r5 = sum(g.get(p) in ("strong", "partial") for p in top5)
            sub = [m[0] for m in ms if m[2] == "submit"]
            sub_ok = sum(g.get(p) in ("strong", "partial") for p in sub)
            near_sub = sum(p in near[ref] for p in sub)
            tot.update(top5=len(top5), s5=s5, r5=r5, sub=len(sub), sub_ok=sub_ok, near_sub=near_sub,
                       cost=float(run[2] or 0))
            print(f"{ref:<6} {s5:>5}/{len(top5):<5} {r5:>4}/{len(top5):<4} {len(sub):>7} {sub_ok:>5}/{len(sub):<3} "
                  f"{near_sub:>11} {','.join(run[1]) or '-':<14} ${float(run[2] or 0):.3f}{' ERR ' + run[3][:150] if run[3] else ''}")
    if not tot["top5"]:
        print("\nno shortlists produced (see errors above)")
        return
    print(f"\nprecision@5 strong: {tot['s5'] / tot['top5']:.1%}   strong-or-partial: {tot['r5'] / tot['top5']:.1%}")
    print(f"'submit' precision (strong or partial): {tot['sub_ok'] / max(tot['sub'], 1):.1%} of {tot['sub']}")
    print(f"near misses recommended 'submit': {tot['near_sub']}   total cost: ${tot['cost']:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
