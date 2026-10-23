"""CLI: python -m placewise.seed <command> [options]"""
import argparse
import collections
import json

from . import facts as F
from .paths import TRUTH, ensure_dirs


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


def main() -> None:
    p = argparse.ArgumentParser(prog="placewise.seed")
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("facts", help="generate candidate facts (ground truth), no LLM")
    f.add_argument("--count", type=int, default=500)
    f.add_argument("--seed", type=int, default=42)
    f.set_defaults(func=cmd_facts)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
