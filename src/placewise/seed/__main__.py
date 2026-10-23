"""CLI: python -m placewise.seed <command> [options]"""
import argparse
import asyncio
import collections
import json

from . import facts as F
from .paths import GENERATED, TRUTH, ensure_dirs


def cmd_facts(args) -> None:
    ensure_dirs()
    cands = F.generate(args.count, seed=args.seed)
    out = TRUTH / "candidates.jsonl"
    with out.open("w") as f:
        for c in cands:
            f.write(json.dumps({**c.model_dump(), "license_codes": c.license_codes}) + "\n")
    print(f"wrote {len(cands)} candidates → {out}")
    print_stats(cands)


def print_stats(cands) -> None:
    def show(title, counter, total):
        print(f"\n{title}")
        for k, v in counter.most_common():
            print(f"  {k:<34} {v:>5}  {v / total:5.1%}")

    n = len(cands)
    show("Discipline", collections.Counter(c.discipline for c in cands), n)
    show("Metro", collections.Counter(c.metro for c in cands), n)
    show("Variant", collections.Counter(c.variant for c in cands), n)
    show("Split", collections.Counter(c.split for c in cands), n)
    show("File format", collections.Counter(c.style.file_format for c in cands), n)
    show("Credentials held (license_codes)", collections.Counter(x for c in cands for x in c.license_codes), n)
    show("Tricky cases", collections.Counter(t for c in cands for t in c.tricky), n)
    yrs = sorted(c.years_experience for c in cands)
    print(f"\nYears of experience: min {yrs[0]}, median {yrs[n // 2]}, max {yrs[-1]}")
    print(f"Unique people: {len({c.person_id for c in cands})}")


def load_facts() -> list[F.CandidateFacts]:
    with (TRUTH / "candidates.jsonl").open() as f:
        return [F.CandidateFacts.model_validate(json.loads(line)) for line in f]


def load_generated() -> dict[str, dict]:
    path = GENERATED / "resumes.jsonl"
    if not path.exists():
        return {}
    with path.open() as f:
        return {r["candidate_id"]: r for r in map(json.loads, f)}


def save_generated(rows: dict[str, dict]) -> None:
    path = GENERATED / "resumes.jsonl"
    tmp = path.with_suffix(".tmp")
    with tmp.open("w") as f:
        for cid in sorted(rows):
            f.write(json.dumps(rows[cid]) + "\n")
    tmp.replace(path)  # atomic: never leaves a half-written file


def cmd_write(args) -> None:
    from . import progress
    from .writer import PROMPT_VERSION, write_many

    ensure_dirs()
    cands = load_facts()
    done = load_generated()
    originals = [c for c in cands if c.variant in ("original", "updated")]
    if args.ids:
        wanted = set(args.ids.split(","))
        originals = [c for c in originals if c.candidate_id in wanted]
    todo = [c for c in originals if args.force or c.candidate_id not in done]
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(todo)} resumes to write ({len(done)} already done, concurrency {args.concurrency})")
    prog = progress.Progress(stage="writing resumes", total=len(todo))

    def on_done(r):
        prog.update(r)
        if r.ok:
            done[r.candidate_id] = {"candidate_id": r.candidate_id, "text": r.text, "prompt_version": PROMPT_VERSION,
                                    "attempts": r.attempts, "input_tokens": r.input_tokens,
                                    "output_tokens": r.output_tokens}
        status = "ok " if r.ok else "REJ"
        print(f"  {status} {r.candidate_id} attempts={r.attempts} {r.seconds}s"
              + ("" if r.ok else f"  problems={r.problems[:3]}"), flush=True)
        if prog.done % 25 == 0:
            save_generated(done)

    results = asyncio.run(write_many(todo, concurrency=args.concurrency, on_done=on_done))
    # Duplicates reuse their source person's text (same person, same resume content)
    by_person = {c.person_id: c.candidate_id for c in cands if c.variant == "original"}
    for c in cands:
        if c.variant in ("exact_duplicate", "format_duplicate") and by_person.get(c.person_id) in done:
            src = done[by_person[c.person_id]]
            done[c.candidate_id] = {**src, "candidate_id": c.candidate_id, "copied_from": src["candidate_id"]}
    save_generated(done)
    prog.finish()
    ok = sum(r.ok for r in results)
    retried = sum(1 for r in results if r.ok and r.attempts > 1)
    cost = sum(r.cost_usd for r in results)
    print(f"\naccepted {ok}/{len(results)}  (needed a retry: {retried}, rejected: {len(results) - ok})")
    print(f"tokens in/out: {sum(r.input_tokens for r in results):,} / {sum(r.output_tokens for r in results):,}"
          f"   cost ≈ ${cost:.3f}")


def main() -> None:
    p = argparse.ArgumentParser(prog="placewise.seed")
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("facts", help="generate candidate facts (ground truth), no LLM")
    f.add_argument("--count", type=int, default=500)
    f.add_argument("--seed", type=int, default=42)
    f.set_defaults(func=cmd_facts)
    w = sub.add_parser("write", help="write resume text with the LLM and fact-check it")
    w.add_argument("--limit", type=int, default=0, help="only write this many (0 = all)")
    w.add_argument("--ids", default="", help="comma-separated candidate ids")
    w.add_argument("--concurrency", type=int, default=8)
    w.add_argument("--force", action="store_true", help="rewrite even if already done")
    w.set_defaults(func=cmd_write)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
