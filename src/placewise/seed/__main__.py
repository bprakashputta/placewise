"""CLI: python -m placewise.seed <command> [options]"""
import argparse
import asyncio
import collections
import json
from pathlib import Path

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
    from .public import publish
    publish()
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
            done[r.candidate_id] = {"candidate_id": r.candidate_id, "text": r.text,
                                    "resume": r.resume.model_dump(), "prompt_version": PROMPT_VERSION,
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


def cmd_render(args) -> None:
    import shutil

    from . import noise
    from .paths import RESUMES
    from .render import render_file

    ensure_dirs()
    facts = {c.candidate_id: c for c in load_facts()}
    gen = load_generated()
    if args.ids:
        wanted = set(args.ids.split(","))
        gen = {k: v for k, v in gen.items() if k in wanted}
    rendered, by_cid = [], {}
    # Originals first, so exact duplicates can copy their source file byte-for-byte
    order = sorted(gen, key=lambda cid: (facts[cid].variant == "exact_duplicate", cid))
    for cid in order:
        row, c = gen[cid], facts[cid]
        if c.variant == "exact_duplicate" and row.get("copied_from") in by_cid:
            src = by_cid[row["copied_from"]]
            dest = RESUMES / cid
            dest.mkdir(parents=True, exist_ok=True)
            for old in dest.iterdir():
                old.unlink()
            shutil.copy2(RESUMES / src["path"], dest / Path(src["path"]).name)
            info = {**src, "candidate_id": cid, "path": f"{cid}/{Path(src['path']).name}", "note": "exact copy"}
            row["text_final"] = gen[row["copied_from"]]["text_final"]
        else:
            from .resume_schema import StructuredResume
            noisy, bullet, applied = noise.apply_structured(row["resume"], c)
            text = StructuredResume.model_validate(noisy).to_text().replace("\n- ", f"\n{bullet} ")
            r = render_file(noisy, text, c, RESUMES, bullet=bullet)
            info = r.__dict__ | {"noise": applied}
            row["text_final"] = text
        by_cid[cid] = info
        rendered.append(info)
    all_gen = load_generated()
    all_gen.update(gen)
    save_generated(all_gen)
    with (GENERATED / "files.jsonl").open("w") as f:
        for info in sorted(rendered, key=lambda i: i["candidate_id"]):
            f.write(json.dumps(info) + "\n")
    fmt = collections.Counter(i["file_format"] for i in rendered)
    notes = collections.Counter(i["note"] for i in rendered if i.get("note"))
    from .public import publish
    publish()
    print(f"rendered {len(rendered)} files → {RESUMES}  formats={dict(fmt)}  special={dict(notes)}")


def cmd_samples(args) -> None:
    """One PDF per template from dev-split candidates, for visual review before a full run."""
    from .paths import RESUMES
    from .render import render_pdf
    from .writer import PROMPT_VERSION, write_many

    ensure_dirs()
    cands = [c for c in load_facts() if c.split == "dev" and c.variant == "original" and not c.unreadable
             and not c.injection]
    picks, seen = [], set()
    for c in cands:
        if c.style.template not in seen and c.style.length != "short":
            picks.append(c)
            seen.add(c.style.template)
    done = load_generated()
    from .resume_schema import StructuredResume
    from .writer import WriteResult
    have = {c.candidate_id for c in picks if done.get(c.candidate_id, {}).get("prompt_version") == PROMPT_VERSION}
    fresh = iter(asyncio.run(write_many([c for c in picks if c.candidate_id not in have], concurrency=5)))
    results = [WriteResult(c.candidate_id, resume=StructuredResume.model_validate(done[c.candidate_id]["resume"]),
                           attempts=0) if c.candidate_id in have else next(fresh) for c in picks]
    out = Path("/app/outputs/samples")
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.pdf"):
        old.unlink()
    for c, r in zip(picks, results):
        if not r.ok:
            print(f"REJ {c.candidate_id}: {r.problems[:3]}")
            continue
        done[c.candidate_id] = {"candidate_id": c.candidate_id, "text": r.text, "resume": r.resume.model_dump(),
                                "prompt_version": PROMPT_VERSION, "attempts": r.attempts,
                                "input_tokens": r.input_tokens, "output_tokens": r.output_tokens}
        name = out / f"{c.style.template}_{c.candidate_id}_{c.first_name}_{c.last_name}.pdf"
        name.write_bytes(render_pdf(r.resume.model_dump(), c, c.style.template))
        print(f"ok  {name.name}  ({c.discipline}, {c.years_experience} yrs, {c.style.persona}/{c.style.length}, "
              f"attempts={r.attempts})")
    save_generated(done)
    print(f"cost ≈ ${sum(r.cost_usd for r in results):.3f}")


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
    r = sub.add_parser("render", help="add code noise and render PDF/DOCX/TXT files")
    r.add_argument("--ids", default="", help="comma-separated candidate ids")
    r.set_defaults(func=cmd_render)
    sm = sub.add_parser("samples", help="one PDF per template (dev split) for visual review")
    sm.set_defaults(func=cmd_samples)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
