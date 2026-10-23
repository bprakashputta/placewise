"""Where seed data lives (inside the `seed` container, /app/data is the repo's ./data).

    data/seed/truth/      ANSWER KEY: candidate facts, job-order specs, relevance labels.
                          Mounted ONLY into the seed and eval containers, never into the app.
    data/seed/generated/  Resume texts and job-order notes as the app will see them (no answers).
    data/seed/resumes/    Rendered PDF/DOCX/TXT files (gitignored; rebuilt from generated/).
    data/seed/public/     Progress, aggregate stats and a few dev-split showcase samples
                          for the live Seed page. Safe to mount read-only into the api.
"""
import os
from pathlib import Path

DATA = Path(os.environ.get("PLACEWISE_DATA_DIR", "/app/data")) / "seed"
TRUTH = DATA / "truth"
GENERATED = DATA / "generated"
RESUMES = DATA / "resumes"
PUBLIC = DATA / "public"


def ensure_dirs() -> None:
    for d in (TRUTH, GENERATED, RESUMES, PUBLIC):
        d.mkdir(parents=True, exist_ok=True)
