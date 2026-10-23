"""End-to-end ingest eval: what the app STORED vs the answer key, for every seed resume.

    docker compose run --rm --entrypoint python seed -m placewise.evals.ingest_db

Checks outcome routing (processed / duplicate / needs attention), duplicate and version linking,
licenses+state, years, metro, discipline, quality labels, plus total cost and chunk counts.
"""
import collections
import json
import statistics

import psycopg

from placewise.config import get_settings
from placewise.seed.facts import CandidateFacts
from placewise.seed.paths import TRUTH


def main() -> None:
    cands = {c.candidate_id: c for c in (CandidateFacts.model_validate(json.loads(l))
                                         for l in (TRUTH / "candidates.jsonl").open())}
    with psycopg.connect(get_settings().database_url) as conn:
        jobs = {r[0]: r for r in conn.execute(
            "SELECT source_ref, status, resume_file_id, result FROM ingest_jobs WHERE source = 'seed'")}
        files = {r[0]: r for r in conn.execute(
            "SELECT id, person_id, status, quality, quality_issues, is_current FROM resume_files")}
        profiles = {r[0]: r for r in conn.execute(
            "SELECT resume_file_id, license_codes, years_experience, metro, discipline FROM profiles")}
        cost = conn.execute("SELECT round(sum(cost_usd), 2), count(*) FROM llm_calls "
                            "WHERE step = 'ingest.extract'").fetchone()
        chunks = conn.execute("SELECT count(*), count(embedding) FROM chunks").fetchone()

    missing = [cid for cid in cands if cid not in jobs]
    status = collections.Counter(jobs[cid][1] for cid in cands if cid in jobs)
    exp = {"unusable": "needs_attention"}
    routing_ok = 0
    for cid, c in cands.items():
        j = jobs.get(cid)
        if not j:
            continue
        want = "duplicate" if c.variant == "exact_duplicate" else exp.get(c.quality, "done")
        routing_ok += j[1] == want

    # Person linking: exact/format duplicates and updated resumes must map to the original's person
    person_of = {cid: files[jobs[cid][2]][1] for cid in cands if cid in jobs and jobs[cid][2] in files}
    by_pid = collections.defaultdict(list)
    for cid, c in cands.items():
        by_pid[c.person_id].append(cid)
    link_ok = link_n = 0
    for pid, cids in by_pid.items():
        if len(cids) < 2:
            continue
        ps = {person_of.get(c) for c in cids if person_of.get(c)}
        link_n += 1
        link_ok += len(ps) == 1
    distinct_truth = len({c.person_id for c in cands.values() if not c.unreadable})
    distinct_app = len({p for p in person_of.values() if p})

    lic_exact = lic_n = 0
    yerr, metro_ok, disc_ok = [], 0, 0
    q_pairs = collections.Counter()
    for cid, c in cands.items():
        j = jobs.get(cid)
        if not j or j[1] != "done":
            if j and j[1] == "needs_attention":
                q_pairs[(c.quality, "unusable")] += 1
            continue
        fid = j[2]
        pr, f = profiles.get(fid), files.get(fid)
        if not pr:
            continue
        lic_n += 1
        lic_exact += set(pr[1]) == set(c.license_codes)
        if pr[2] is not None:
            yerr.append(abs(pr[2] - c.years_experience))
        metro_ok += pr[3] == c.metro
        disc_ok += pr[4] == c.discipline
        q_pairs[(c.quality, f[3])] += 1

    def pr_(label):
        tp = q_pairs.get((label, label), 0)
        fp = sum(n for (t, d), n in q_pairs.items() if d == label and t != label)
        fn = sum(n for (t, d), n in q_pairs.items() if t == label and d != label)
        return (tp / (tp + fp) if tp + fp else 1.0), (tp / (tp + fn) if tp + fn else 1.0)

    print(f"seed resumes: {len(cands)}   jobs found: {len(cands) - len(missing)}   missing: {len(missing)}")
    print(f"job outcomes: {dict(status)}")
    print(f"routing correct (processed / duplicate / needs attention): {routing_ok}/{len(cands)}")
    print(f"multi-file people linked to ONE person: {link_ok}/{link_n}   "
          f"distinct people: app {distinct_app} vs truth {distinct_truth}")
    print(f"licenses+state exact: {lic_exact}/{lic_n} = {lic_exact / max(lic_n, 1):.1%}")
    print(f"years MAE: {statistics.mean(yerr):.2f}  within 1 yr: {sum(e <= 1 for e in yerr) / len(yerr):.1%}")
    print(f"metro accuracy: {metro_ok / lic_n:.1%}   discipline accuracy: {disc_ok / lic_n:.1%}")
    for label in ("unusable", "adversarial", "flawed"):
        p, r = pr_(label)
        print(f"quality '{label}': precision {p:.0%} recall {r:.0%}")
    print(f"extraction calls: {cost[1]}  cost: ${cost[0]}  (≈ ${float(cost[0]) / max(cost[1], 1):.3f}/resume)")
    print(f"chunks: {chunks[0]} (with embeddings: {chunks[1]})")
    print("quality (truth → detected):", dict(q_pairs))


if __name__ == "__main__":
    main()
