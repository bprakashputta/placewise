-- Placewise database tour (read-only). Never selects email, phone or password columns.
\pset border 2
\pset null '–'
\echo '\n=== 1. Tables and row counts ==='
SELECT relname AS table, n_live_tup AS rows FROM pg_stat_user_tables ORDER BY relname;

\echo '\n=== 2. Candidates (current profile per person; synthetic data only) ==='
SELECT c.person_id, c.full_name, c.discipline, c.metro, c.years_experience AS yrs, c.license_codes, c.quality
FROM current_candidates c JOIN resume_files rf ON rf.id = c.resume_file_id AND rf.source = 'seed'
ORDER BY c.person_id LIMIT 10;

\echo '\n=== 3. One structured profile, with evidence quotes for credentials ==='
SELECT p.full_name, c->>'key' AS credential, c->>'state' AS state, c->>'status' AS status, c->>'quote' AS quote_from_resume
FROM profiles p JOIN resume_files rf ON rf.id = p.resume_file_id AND rf.is_current,
     jsonb_array_elements(p.data->'credentials') c
WHERE p.license_codes @> ARRAY['PE:TX'] LIMIT 6;

\echo '\n=== 4. Searchable resume sections (what vector + keyword search run on) ==='
SELECT person_id, section,
       left(regexp_replace(regexp_replace(content, '^\[[^]]*\]\s*', ''), '[^ -~]', ' ', 'g'), 80) AS content,
       vector_dims(embedding) AS embedding_dims
FROM current_chunks ORDER BY person_id, ordinal LIMIT 6;

\echo '\n=== 5. Pool by discipline and metro ==='
SELECT discipline, metro, count(*) AS candidates FROM current_candidates GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 12;

\echo '\n=== 6. Job orders and their latest match run ==='
SELECT j.id, j.title, j.spec->>'metro' AS metro, jsonb_array_length(j.spec->'requirements') AS reqs,
       (SELECT count(*) FROM matches m WHERE m.job_order_id = j.id AND m.recommendation = 'submit') AS submit_suggestions
FROM job_orders j ORDER BY j.id LIMIT 16;

\echo '\n=== 7. A shortlist: score computed by code, verdicts with quotes ==='
SELECT c.full_name, m.score, m.recommendation, m.status,
       v->>'requirement' AS requirement, v->>'verdict' AS verdict, left(coalesce(v->>'evidence', v->>'note'), 70) AS evidence_or_note
FROM matches m JOIN current_candidates c ON c.person_id = m.person_id, jsonb_array_elements(m.verdicts) v
WHERE m.run_id = (SELECT run_id FROM match_runs WHERE job_order_id = 3 AND status = 'done' ORDER BY started_at DESC LIMIT 1)
ORDER BY m.score DESC, c.full_name LIMIT 14;

\echo '\n=== 8. Ingest queue outcomes ==='
SELECT status, count(*) FROM ingest_jobs GROUP BY 1 ORDER BY 2 DESC;

\echo '\n=== 9. AI cost log by step and model ==='
SELECT step, model, count(*) AS calls, round(sum(cost_usd), 4) AS cost_usd, round(avg(latency_ms)) AS avg_ms
FROM llm_calls GROUP BY 1, 2 ORDER BY cost_usd DESC NULLS LAST;
