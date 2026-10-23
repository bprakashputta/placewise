"""Publish what the live Seed page may show into data/seed/public/ (mounted read-only into the api).

Allowed: aggregate counts, the file list, and full details for a few DEV-split showcase
candidates. Never per-candidate answers for the TEST split, which is reserved for evals.
"""
import collections
import json
import time

from .paths import GENERATED, PUBLIC, TRUTH


def _read_jsonl(path):
    if not path.exists():
        return []
    with path.open() as f:
        return [json.loads(line) for line in f]


def publish(showcase_n: int = 12) -> dict:
    cands = _read_jsonl(TRUTH / "candidates.jsonl")
    files = {r["candidate_id"]: r for r in _read_jsonl(GENERATED / "files.jsonl")}
    gen = {r["candidate_id"]: r for r in _read_jsonl(GENERATED / "resumes.jsonl")}
    jos = _read_jsonl(TRUTH / "job_orders.jsonl")
    notes = {r["job_order_id"]: r for r in _read_jsonl(GENERATED / "job_orders.jsonl")}

    def count(fn):
        return dict(collections.Counter(x for c in cands for x in fn(c)).most_common())

    stats = {
        "candidates": len(cands),
        "people": len({c["person_id"] for c in cands}),
        "written": len(gen),
        "rendered": len(files),
        "by_discipline": count(lambda c: [c["discipline"]]),
        "by_metro": count(lambda c: [c["metro"]]),
        "by_format": dict(collections.Counter(f["file_format"] for f in files.values())),
        "by_split": count(lambda c: [c["split"]]),
        "credentials": count(lambda c: c["license_codes"]),
        "tricky": count(lambda c: c["tricky"]),
        "quality": count(lambda c: [c.get("quality", "polished")]),
        "job_orders": len(jos),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    # Showcase PDFs only, so anyone can open them in the browser (owner request)
    showcase_pool = [c for c in cands if c["split"] == "dev" and c["candidate_id"] in files
                     and files[c["candidate_id"]]["file_format"] == "pdf" and not c["unreadable"]]
    # Prefer variety: one per discipline, then the interesting edge cases
    picked, seen = [], set()
    for c in showcase_pool:
        if c["discipline"] not in seen:
            picked.append(c)
            seen.add(c["discipline"])
    # Then deliberately flawed examples, so the labels are visible next to polished ones
    for c in showcase_pool:
        if len(picked) >= showcase_n:
            break
        if c.get("quality") in ("flawed", "adversarial") and c not in picked:
            picked.append(c)
    showcase = [{
        "candidate_id": c["candidate_id"], "name": f"{c['first_name']} {c['last_name']}",
        "discipline": c["discipline"], "metro": c["metro"], "city": c["city"],
        "years_experience": c["years_experience"], "current_title": c["current_title"],
        "current_employer": c["current_employer"], "license_codes": c["license_codes"],
        "credential_texts": [x["text"] for x in c["credentials"]], "software": c["software"],
        "tricky": c["tricky"], "variant": c["variant"],
        "quality": c.get("quality", "polished"), "quality_issues": c.get("quality_issues", []),
        "file": files[c["candidate_id"]]["path"], "file_format": files[c["candidate_id"]]["file_format"],
        "template": files[c["candidate_id"]]["template"], "note": files[c["candidate_id"]].get("note", ""),
        "text_preview": (gen.get(c["candidate_id"], {}).get("text_final") or "")[:1500],
    } for c in picked[:showcase_n]]
    dev_ids = {c["candidate_id"] for c in cands if c["split"] == "dev"}
    file_list = [{"candidate_id": f["candidate_id"], "path": f["path"], "file_format": f["file_format"],
                  "template": f["template"], "bytes": f["bytes"], "has_preview": bool(f.get("preview"))
                  or f["file_format"] == "pdf",
                  "note": f.get("note", "") if f["candidate_id"] in dev_ids else ""}
                 for f in sorted(files.values(), key=lambda f: f["candidate_id"])]
    job_orders = [{"job_order_id": j["job_order_id"], "title": j["title"], "split": j["split"],
                   "notes": notes.get(j["job_order_id"], {}).get("notes"),
                   "spec": j if j["split"] == "dev" else None} for j in jos]
    PUBLIC.mkdir(parents=True, exist_ok=True)
    for name, data in (("stats.json", stats), ("showcase.json", showcase), ("files.json", file_list),
                       ("job_orders.json", job_orders)):
        tmp = PUBLIC / f"{name}.tmp"
        tmp.write_text(json.dumps(data))
        tmp.replace(PUBLIC / name)
    return stats
