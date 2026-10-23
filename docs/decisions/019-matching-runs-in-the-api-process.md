# 019: Match runs execute inside the API process (for now)

- **Status:** accepted, known limitation (raised in the PR #2 review)
- **Date:** 2026-10-23

## Context
AGENTS.md describes a stateless `api` and a `worker` that runs LangGraph jobs from the Postgres
`SKIP LOCKED` queue. Ingest follows that design. Matching (Block 6) doesn't: `POST /api/job-orders/{id}/match`
starts the run with `asyncio.create_task` inside the API process, and the browser polls for the result.
A run takes 20–40 s (12 scoring calls, at most 6 at a time).

## Decision
Keep in-process runs for the demo, with these guards:
- **One run at a time per job order, enforced by the database:** a partial unique index
  `match_runs_one_running (job_order_id) WHERE status = 'running'` (migration 007). A second click gets 409.
- **No stuck runs:** at startup every `running` row is marked failed (the process that owned it is gone),
  and a run older than 10 minutes is reported as timed out.
- **Bounded cost:** the spend check runs before the run starts and before every scoring call.

## Alternatives considered
- **Run matching on the existing job queue (worker):** the right long-term design. It gives leases, retries and
  restarts that don't lose work, and the API stays stateless. It needs a `match` job kind, a worker handler, and
  progress reporting through the database. It wasn't done before the demo.
- **A separate task system (Celery, Arq):** another moving part when the Postgres queue already exists.

## Tradeoffs and consequences
- **Gain:** simple, fast to build, and easy to follow in one process and one LangSmith trace.
- **Give up:**
  - A deploy or restart loses runs in flight (they're marked failed and can be rerun).
  - **With more than one API replica**, the startup sweep would also fail runs another replica is still
    processing. So the API must stay at one replica until runs move to the worker.
- **Revisit when:** a second API replica is needed, or runs get longer. Then move matching onto the job queue
  (planned with Block 8/9).
