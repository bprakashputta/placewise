# API contract (Block 3)

The web app talks only to `/api/*` (proxied same-origin to FastAPI). All JSON. Every route needs a
logged-in session cookie (`pw_session`, httpOnly, SameSite=Lax), except `GET /api/health` and
`POST /api/auth/login`. Without a session the API returns **401** `{"detail": "..."}`. A recruiter
calling an admin-only route gets **403**.

## Auth
| Method | Path | Body / query | Response |
|---|---|---|---|
| POST | `/api/auth/login` | `{"username", "password"}` | 200 `{"user": {"username","display_name","role"}}` + sets cookie · 401 bad credentials · 429 too many attempts |
| POST | `/api/auth/logout` | – | 200 `{"ok": true}` (clears cookie) |
| GET | `/api/auth/me` | – | 200 `{"user": {...}}` · 401 |

Roles: `admin` (everything) and `recruiter` (everything except admin-only routes, marked 🔒).

## Dashboard
`GET /api/stats` → `{"candidates": int, "needs_attention": int, "files_processed": int,
"ingest_jobs": {"done": n, "queued": n, ...}, "by_quality": {"polished": n, ...},
"ai_spend_today_usd": float, "ai_spend_total_usd": float, "spend_cap_usd": float, "open_job_orders": int, "shortlists_to_review": int}`

## Candidates
| Method | Path | Notes |
|---|---|---|
| GET | `/api/candidates?q=&discipline=&metro=&license=&min_years=&quality=&limit=50&offset=0` | `{"total", "limit", "offset", "items": [{person_id, full_name, headline, discipline, subdiscipline, city, state, metro, years_experience, license_codes[], quality, quality_issues[], processed_at}]}` |
| GET | `/api/candidates/facets` | `{"discipline": {value: count}, "metro": {...}, "quality": {...}, "license": {"PE:TX": n, ...}, "files": {...}}` |
| GET | `/api/candidates/needs-attention` | `[{resume_file_id, filename, quality_issues[], reason, created_at}]` |
| GET | `/api/candidates/{person_id}` | `{person_id, resume_file_id, filename, quality, quality_issues[], processed_at, years_experience, metro, license_codes[], software[], sectors[], findings[], validation_notes[], versions[{resume_file_id, filename, status, quality, is_current, created_at, processed_at}], profile: {full_name, headline, discipline, subdiscipline, summary, city, state, open_to_relocation, jobs[{title, employer, location, start, end, highlights[]}], credentials[{quote, key, state, status}], software[], sectors[], education[{degree, school, year}], writing_quality: {rating, issues[], evidence[]}}}` (no email/phone) |
| GET | `/api/candidates/files/{resume_file_id}/view` | inline PDF, or 404 JSON `{"detail"}` when no preview exists |
| GET | `/api/candidates/files/{resume_file_id}` | download the original file |
| POST | `/api/candidates/upload` | multipart `file` → `{"queued": bool, "job_id": int|null, "sha256", "message"}` · 413 too large · 415 bad type/empty |
| GET | `/api/ingest/jobs/{job_id}` | `{id, status, attempts, error, result, resume_file_id, ...}`; status: queued, running, done, duplicate, needs_attention, failed. `result.person_id` is set when done |

## Admin 🔒
| GET | `/api/admin/costs` | `{"spend_cap_usd", "spent_today_usd", "by_day": [{day, calls, cost_usd}], "by_step_model": [{step, model, calls, input_tokens, output_tokens, cost_usd}]}` |
| GET | `/api/ingest/summary` (any signed-in user) | `{"jobs": {status: n}}` |
| POST | `/api/ingest/jobs/retry-failed` | `{"requeued": n}` |

Display rules for the UI:
- License codes like `PE:TX` show as "PE · TX". Quality labels: polished (green), flawed (amber),
  unusable (red), adversarial (fuchsia).
- Credentials always show their **quote** (the exact resume text) as evidence, plus the status (active,
  pursuing, exam_scheduled, expired). Only "active" counts toward license_codes.
- Never show email/phone (the API doesn't return them).

## Ask (RAG) and smart search (Block 5)
| Method | Path | Notes |
|---|---|---|
| POST | `/api/ask` | body `{"question": str, "filters"?: {discipline, metro, license_codes[], min_years}}` → `{"question", "answer" (markdown), "citations": [{chunk_id, person_id, resume_file_id, candidate_name, section, quote}], "candidates": [{person_id, full_name, headline, discipline, metro, city, years_experience, license_codes[], quality, score, top_sections[{chunk_id, section, content}]}], "plan": {"filters": {...}, "search_query"}, "dropped_citations": [str], "timings_ms": {understand_ms, retrieve_ms, rerank_ms, answer_ms, total_ms}, "cost_usd"}` · 429 when the daily AI spend cap is reached. Takes ~10–15 s. |
| GET | `/api/search?q=&discipline=&metro=&license=&min_years=&limit=20` | No LLM, ~0.5 s: `{"query", "items": [{person_id, full_name, headline, discipline, metro, city, years_experience, license_codes[], quality, score, match (clean excerpt)}]}` |

## Job orders + matching (Blocks 4 + 6)
| Method | Path | Notes |
|---|---|---|
| POST | `/api/job-orders` | body `{"notes": str (20–6000 chars)}` → `{id, title, client, raw_notes, spec, status, created_at, cost_usd}` (~8 s). `spec` = `{title, client, city, metro, work_mode, employment_type, salary, discipline, subdiscipline, min_years, requirements[{text, kind, priority: must|nice, key, state, value}], open_questions[]}` |
| GET | `/api/job-orders` | `[{id, title, client, status, created_at, metro, discipline, last_run_id, last_run_status, last_run_at, submit_count, pending_review}]` |
| GET | `/api/job-orders/{id}` | `{id, title, client, raw_notes, spec, status, created_at}` |
| POST | `/api/job-orders/{id}/match` | starts a background match run → `{run_id, status: "running"}` (takes ~20–40 s) |
| GET | `/api/job-orders/{id}/matches?run_id=` | latest (or given) run: `{"run": {run_id, status: running|done|failed, filters, relaxed[], candidates, cost_usd, error, started_at, finished_at}, "matches": [{id, person_id, resume_file_id, score (0–100), recommendation: submit|consider|pass, verdicts[{requirement, verdict: met|partial|not_met|unknown, evidence, note}], flags[], summary, retrieval_rank, status: proposed|approved|rejected, full_name, headline, metro, years_experience, license_codes[], quality}]}`. Poll every 2 s while running |
| POST | `/api/matches/{id}/decision` | `{"status": "approved"|"rejected"|"proposed"}` (recruiter decision) |

UI notes: the score is computed by code from the verdicts (must-haves weigh 3×, nice-to-haves 1×). Show
each requirement as a row with a verdict icon (✓ met, ◐ partial, ✕ not met, ? unknown), the evidence
quote, and the note (e.g. "License is in another state: PE:OK"). `relaxed` lists filters that were
loosened because too few candidates qualified: show it as a notice.

## Conversations: conversational Ask (Block 7, ADR 018)
A recruiter's Ask chats are saved as **conversations** (each user sees only their own). Each message is
routed first: greetings, help and off-topic messages get an instant reply with no search; only candidate
questions run the RAG pipeline. Follow-ups ("which of those have PMP?") reuse the previous answer's candidates.

| Method | Path | Notes |
|---|---|---|
| GET | `/api/conversations` | `[{id, title, job_order_id, job_order_title, active, created_at, last_message_at, message_count, has_search}]` (`has_search`: the chat holds a real answer, not just small talk), newest first, max 50. `active` = a message in the last 24 h and the job order (if any) is still open |
| POST | `/api/conversations` | body `{"job_order_id"?: int}` → the new conversation `{id, title, job_order_id, job_order_title, active, created_at, last_message_at, message_count, messages: [...]}`. A conversation tied to a job order starts with one assistant `intro` message. 404 if the job order doesn't exist |
| GET | `/api/conversations/{id}` | `{id, title, job_order_id, job_order_title, active, created_at, last_message_at, message_count, messages: [Message]}` · 404 if not yours |
| POST | `/api/conversations/{id}/messages` | body `{"content": str (1–2000 chars, not blank)}` → `{"user_message": Message, "assistant_message": Message}`. Greetings take <1 s; searches ~10–15 s. 429 at the spend cap (nothing is saved). 404 if not yours |

`Message` = `{id, role: "user"|"assistant", kind, content, response, suggestions: [str], created_at}`
- `kind` (assistant): `greeting` · `help` · `off_topic` · `intro` · `search` · `follow_up` · `job_order`. User messages have `kind: "user"`.
- `content`: Markdown text to show. For search kinds it's the answer text.
- `response`: for search kinds, the same object `POST /api/ask` returns (citations, candidates, plan, timings, cost), plus `"standalone_question"`: the complete question that was searched (e.g. "Of the 8 candidates above, which have an active PMP?"). `null` for other kinds.
- `suggestions`: 0–3 short follow-up prompts to show as clickable chips (clicking sends that text).
