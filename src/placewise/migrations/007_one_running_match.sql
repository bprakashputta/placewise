-- 007: at most one running match per job order, enforced by the database (PR #2 review).
-- An app-level check alone can race: two quick clicks could both pass it and start two paid runs.
-- Any row still 'running' at migration time belongs to a process that has already stopped.
UPDATE match_runs SET status = 'failed', error = 'interrupted (server restarted)', finished_at = now()
WHERE status = 'running';
CREATE UNIQUE INDEX match_runs_one_running ON match_runs (job_order_id) WHERE status = 'running';
