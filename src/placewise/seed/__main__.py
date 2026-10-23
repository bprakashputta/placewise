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
    # Redo anything missing or written with an older prompt version
    todo = [c for c in originals if args.force or c.candidate_id not in done
            or done[c.candidate_id].get("prompt_version") != PROMPT_VERSION]
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
    from .writer import PROMPT_VERSION
    # Only render resumes written in the current structured format; others wait for a rewrite
    stale = [cid for cid, row in gen.items() if "resume" not in row and not row.get("copied_from")]
    gen = {cid: row for cid, row in gen.items() if cid not in stale and cid in facts}
    if stale:
        print(f"skipping {len(stale)} resumes not yet in the current format (prompt v{PROMPT_VERSION})")
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
    # Merge into the existing index: a partial render (--ids) must not drop other files
    index_path = GENERATED / "files.jsonl"
    index = {}
    if index_path.exists():
        index = {r["candidate_id"]: r for r in map(json.loads, index_path.open())}
    index.update({i["candidate_id"]: i for i in rendered})
    index = {cid: i for cid, i in index.items() if cid in facts}
    tmp = index_path.with_suffix(".tmp")
    with tmp.open("w") as f:
        for cid in sorted(index):
            f.write(json.dumps(index[cid]) + "\n")
    tmp.replace(index_path)
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


def cmd_job_orders(args) -> None:
    """Add targeted candidates, write recruiter notes (LLM), and build the matching answer key."""
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, SystemMessage

    from . import job_orders as J
    from . import prompts as P
    from .facts import split_for

    ensure_dirs()
    cands = [c for c in load_facts() if not c.targets_job_order]          # idempotent: rebuild targets
    targeted = J.targeted_candidates(start_index=len(cands) + 1, seed=args.seed)
    allc = cands + targeted
    with (TRUTH / "candidates.jsonl").open("w") as f:
        for c in allc:
            f.write(json.dumps({**c.model_dump(), "license_codes": c.license_codes}) + "\n")
    print(f"targeted candidates: {len(targeted)} (total candidates now {len(allc)})")

    # Job-order truth (specs) and their split
    with (TRUTH / "job_orders.jsonl").open("w") as f:
        for jo in J.SPECS:
            f.write(jo.model_dump_json() + "\n")

    # Answer key: every pair graded; store strong/partial plus every targeted candidate's row
    key, counts = [], collections.Counter()
    for jo in J.SPECS:
        for c in allc:
            lab = J.label(c, jo)
            if lab["grade"] != "none" or (c.targets_job_order or "").startswith(jo.job_order_id):
                key.append(lab)
            counts[(jo.job_order_id, lab["grade"])] += 1
    with (TRUTH / "relevance.jsonl").open("w") as f:
        for row in key:
            f.write(json.dumps(row) + "\n")
    print("\njob order                          strong partial")
    for jo in J.SPECS:
        flag = "  (designed to have no strong match)" if jo.expect_no_match else ""
        print(f"  {jo.job_order_id} {jo.title[:30]:<30} {counts[(jo.job_order_id, 'strong')]:>6} "
              f"{counts[(jo.job_order_id, 'partial')]:>7}{flag}")

    # Recruiter call notes via LLM (skip ones already written unless --force)
    notes_path = GENERATED / "job_orders.jsonl"
    existing = {}
    if notes_path.exists():
        existing = {r["job_order_id"]: r for r in map(json.loads, notes_path.open())}
    p = P.load("seed_job_order_notes", 1)
    llm = ChatAnthropic(model=p["model"], max_tokens=800, max_retries=4, timeout=60)
    leave = {"work_mode": "onsite/hybrid/remote", "salary": "salary or pay rate",
             "employment_type": "direct hire vs contract"}
    cost = 0.0
    for jo in J.SPECS:
        if jo.job_order_id in existing and not args.force:
            continue
        include = [r.text for r in jo.must_have] + [f"nice to have: {r.text}" for r in jo.nice_to_have]
        for fld in ("work_mode", "salary", "employment_type"):
            if fld not in jo.omit_in_notes:
                include.append(f"{fld.replace('_', ' ')}: {getattr(jo, fld)}")
        include.append(f"location: {jo.city}")
        user = p["user"].format(title=jo.title, client=jo.client, include="\n  ".join(f"- {x}" for x in include),
                                leave_out=", ".join(leave[x] for x in jo.omit_in_notes) or "nothing")
        msg = llm.invoke([SystemMessage(p["system"]), HumanMessage(user)])
        text = msg.content if isinstance(msg.content, str) else "".join(b.get("text", "") for b in msg.content)
        u = msg.usage_metadata or {}
        cost += u.get("input_tokens", 0) / 1e6 * 0.10 + u.get("output_tokens", 0) / 1e6 * 0.50
        existing[jo.job_order_id] = {"job_order_id": jo.job_order_id, "title": jo.title, "notes": text.strip(),
                                     "prompt_version": 1}
        print(f"  notes written: {jo.job_order_id}")
    with notes_path.open("w") as f:
        for jid in sorted(existing):
            f.write(json.dumps(existing[jid]) + "\n")
    print(f"notes cost ≈ ${cost:.4f}")
    _ = split_for
    from .public import publish
    publish()


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
    jo = sub.add_parser("job-orders", help="targeted candidates, recruiter notes, and the matching answer key")
    jo.add_argument("--seed", type=int, default=42)
    jo.add_argument("--force", action="store_true", help="rewrite notes even if they exist")
    jo.set_defaults(func=cmd_job_orders)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
