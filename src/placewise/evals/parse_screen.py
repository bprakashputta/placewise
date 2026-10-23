"""Evaluate parsing + screening (no AI) against the answer key, over every seed resume.

    docker compose run --rm --entrypoint python seed -m placewise.evals.parse_screen

Measures: unusable / adversarial detection (precision & recall), hidden-text false positives,
text coverage (do the true facts appear in the extracted text?), and two-column reading order.
"""
import collections
import json
import re
import time

from placewise.ingest.parse import parse
from placewise.ingest.screen import screen
from placewise.ingest.sources import seed_original
from placewise.seed.factcheck import must_include
from placewise.seed.facts import CandidateFacts
from placewise.seed.paths import TRUTH


def norm(s: str) -> str:
    s = s.replace("–", "-").replace("—", "-").replace(" ", " ")
    return re.sub(r"\s+", " ", s).lower()


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    return p, r


def main() -> None:
    cands = [CandidateFacts.model_validate(json.loads(l)) for l in (TRUTH / "candidates.jsonl").open()]
    t0 = time.perf_counter()
    rows = []
    for c in cands:
        p = parse(seed_original(c.candidate_id).read_bytes())
        s = screen(p)
        rows.append((c, p, s))
    secs = time.perf_counter() - t0

    print(f"parsed {len(rows)} files in {secs:.1f}s ({secs / len(rows) * 1000:.0f} ms/file)\n")
    for label in ("unusable", "adversarial"):
        tp = sum(1 for c, _, s in rows if c.quality == label and s.quality == label)
        fp = sum(1 for c, _, s in rows if c.quality != label and s.quality == label)
        fn = sum(1 for c, _, s in rows if c.quality == label and s.quality != label)
        pr, rc = prf(tp, fp, fn)
        print(f"{label:<12} detection: precision {pr:.0%}  recall {rc:.0%}   (tp {tp}, fp {fp}, fn {fn})")
    hidden_fp = sum(1 for c, p, _ in rows if p.hidden_text and not c.injection)
    print(f"hidden text on non-adversarial files: {hidden_fp}")

    gen = {r["candidate_id"]: r for r in map(json.loads, (TRUTH.parent / "generated" / "resumes.jsonl").open())
           if "resume" in r}
    cov, worst, by_tpl = [], [], collections.defaultdict(list)
    order_ok = order_n = 0
    for c, p, s in rows:
        if p.status != "ok":
            continue
        text = norm(s.clean_text)
        items = must_include(c)
        hit = sum(1 for i in items if norm(i) in text)
        frac = hit / len(items)
        cov.append(frac)
        by_tpl[c.style.template + "/" + p.file_type].append(frac)
        if frac < 1:
            worst.append((frac, c.candidate_id, c.style.template, p.file_type,
                          [i for i in items if norm(i) not in text][:3]))
        if c.style.template == "two_column" and p.file_type == "pdf" and c.candidate_id in gen:
            # Reading order: each job's first bullet (unique text) must appear in job order
            order_n += 1
            jobs = gen[c.candidate_id]["resume"]["jobs"]
            pos = [text.find(norm(j["bullets"][0])[:60]) for j in jobs if j["bullets"]]
            found = [x for x in pos if x >= 0]
            order_ok += len(found) >= max(1, len(pos) - 1) and found == sorted(found)
    print(f"\ntext coverage of true facts (readable files): mean {sum(cov) / len(cov):.1%}, "
          f"files with 100%: {sum(1 for x in cov if x == 1)}/{len(cov)}")
    for k in sorted(by_tpl):
        v = by_tpl[k]
        print(f"  {k:<22} {sum(v) / len(v):6.1%}  (n={len(v)})")
    if order_n:
        print(f"two-column PDFs with jobs in correct reading order: {order_ok}/{order_n}")
    for w in sorted(worst)[:8]:
        print(f"  low coverage {w[0]:.0%} {w[1]} {w[2]}/{w[3]} missing {w[4]}")
    fp_flawed = [(c.candidate_id, s.issues) for c, _, s in rows if c.quality == "polished" and s.quality == "flawed"]
    print("polished but screened flawed:", fp_flawed)
    flawed_detected = collections.Counter((c.quality, s.quality) for c, _, s in rows)
    print("\n(truth quality → screen quality):", dict(flawed_detected))


if __name__ == "__main__":
    main()
