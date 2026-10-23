"""Load versioned prompt files from /app/prompts (repo ./prompts). Prompts never live in code."""
import os
from functools import lru_cache
from pathlib import Path

import yaml

PROMPTS_DIR = Path(os.environ.get("PLACEWISE_PROMPTS_DIR", "/app/prompts"))


@lru_cache
def load(name: str, version: int) -> dict:
    data = yaml.safe_load((PROMPTS_DIR / f"{name}.v{version}.yaml").read_text())
    for key in ("name", "version", "model", "system", "user"):
        if key not in data:
            raise ValueError(f"prompt {name}.v{version} missing '{key}'")
    return data
