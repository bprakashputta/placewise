"""Turn a validated profile into searchable sections (one chunk per meaningful unit).

Each chunk is self-contained: it starts with the candidate's headline, so a retrieved chunk is
understandable on its own. Names and contact details are NOT included (citations show work, not
identity; the person is linked by id).
"""
from __future__ import annotations


def build_chunks(profile: dict) -> list[dict]:
    head = profile.get("headline") or (profile.get("discipline") or "").replace("_", " ")
    ctx = f"{head} | {profile.get('discipline', '').replace('_', ' ')}"
    chunks: list[dict] = []

    def add(section: str, body: str) -> None:
        body = body.strip()
        if body:
            chunks.append({"section": section, "ordinal": len(chunks), "content": f"[{ctx}] {section}: {body}"})

    if profile.get("summary"):
        add("summary", profile["summary"])
    for j in profile.get("jobs", []):
        dates = " - ".join(x for x in (j.get("start"), j.get("end")) if x)
        bullets = " ".join(f"• {h}" for h in j.get("highlights", []))
        add("job", f"{j['title']} at {j['employer']} ({dates}). {bullets}")
    creds = [f"{c['quote']} ({c['status']})" for c in profile.get("credentials", [])]
    if creds:
        add("credentials", "; ".join(creds))
    skills = profile.get("software", []) + profile.get("sectors", [])
    if skills:
        add("skills", "Software: " + ", ".join(profile.get("software", [])) +
            ". Sectors: " + ", ".join(profile.get("sectors", [])))
    edu = [f"{e['degree']}, {e['school']}" for e in profile.get("education", [])]
    if edu:
        add("education", "; ".join(edu))
    return chunks


def blind_text(profile: dict) -> str:
    """Profile text with identity removed (name, contact, location, graduation years), used later for
    scoring so the model judges skills and experience only."""
    parts = [profile.get("headline", ""), profile.get("summary") or ""]
    for j in profile.get("jobs", []):
        parts.append(f"{j['title']}, {j['employer']}, {j.get('start')} - {j.get('end')}: " +
                     " ".join(j.get("highlights", [])))
    parts.append("Credentials: " + "; ".join(f"{c['quote']} ({c['status']})" for c in profile.get("credentials", [])))
    parts.append("Software: " + ", ".join(profile.get("software", [])))
    parts.append("Sectors: " + ", ".join(profile.get("sectors", [])))
    parts.append("Education: " + "; ".join(e["degree"] for e in profile.get("education", [])))  # no school year
    return "\n".join(p for p in parts if p.strip())
