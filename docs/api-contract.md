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
"ai_spend_today_usd": float, "ai_spend_total_usd": float, "spend_cap_usd": float}`

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
| GET | `/api/ingest/summary` | `{"jobs": {status: n}}` |
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
| GET | `/api/search?q=&discipline=&metro=&license=&min_years=&limit=20` | No LLM, ~0.5 s: `{"query", "items": [{person_id, full_name, headline, discipline, metro, years_experience, license_codes[], quality, score, match}]}` |
