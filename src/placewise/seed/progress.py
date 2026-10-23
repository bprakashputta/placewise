"""Live progress for the Seed page: written to data/seed/public/progress.json (no answer-key data)."""
import json
import time

from .paths import PUBLIC


class Progress:
    def __init__(self, stage: str, total: int):
        self.stage, self.total, self.done, self.ok, self.rejected, self.retried = stage, total, 0, 0, 0, 0
        self.cost, self.started = 0.0, time.time()
        self._write("running")

    def update(self, r) -> None:
        self.done += 1
        self.ok += r.ok
        self.rejected += not r.ok
        self.retried += r.ok and r.attempts > 1
        self.cost += r.cost_usd
        self._write("running")

    def finish(self) -> None:
        self._write("done")

    def _write(self, status: str) -> None:
        elapsed = time.time() - self.started
        rate = self.done / elapsed if elapsed > 0 and self.done else 0
        eta = (self.total - self.done) / rate if rate else None
        data = {"stage": self.stage, "status": status, "total": self.total, "done": self.done, "ok": self.ok,
                "rejected": self.rejected, "retried": self.retried, "cost_usd": round(self.cost, 4),
                "elapsed_s": round(elapsed, 1), "eta_s": round(eta, 1) if eta else None,
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        PUBLIC.mkdir(parents=True, exist_ok=True)
        tmp = PUBLIC / "progress.tmp"
        tmp.write_text(json.dumps(data))
        tmp.replace(PUBLIC / "progress.json")
