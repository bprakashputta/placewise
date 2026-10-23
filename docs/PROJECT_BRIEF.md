# Placewise: Project Brief

## Problem
A/E/C recruiting firms win revenue when they fill client job orders with scarce, often licensed professionals (PE, RA, NCIDQ). Recruiters lose time on:
- turning messy hiring-manager calls into clear requirements,
- searching an outdated candidate database by keyword,
- checking credentials (license type **and** state),
- writing submittals and outreach by hand.

The existing candidate database is the top source of placements, but it's under-used.

## Users
- **Recruiter:** creates job orders, reviews shortlists, approves submittals and outreach, asks questions about the candidate pool.
- **Admin:** everything a recruiter can do, plus users, AI cost and quality monitoring, traces and settings.

## What Placewise does (phase 1)
| Workflow | Recruiter sees | Value |
|---|---|---|
| **A. Job order → shortlist + submittals** | Paste notes → structured requirements and clarifying questions → ranked candidates with evidence and flags → one-click submittals → approve | Hours saved per job order |
| **B. Ask anything** | Agent chat and RAG with citations over the candidate pool | Fast answers grounded in real data |
| **C. Bench revival + MPC pitches** (stretch) | Past candidates to re-engage, plus anonymized pitches to client firms | Helps win new job orders |
| **Intake from anywhere** | Resumes from the Apply page, job boards or ATS, email or a folder, all through n8n into one pipeline | One consistent pipeline |

## What Placewise does NOT do
Interview scheduling, offers, placements, billing, compliance. Those stay in the ATS. Placewise is an AI layer, not an ATS.

## Intake sources (n8n workflows)
1. Resume intake webhook (Placewise Apply page, or any job board or ATS pointed at it) **[core]**
2. Bulk folder intake [later]
3. Email intake (job-board alert emails) [later]
4. Job order intake → auto-match → notify recruiter **[core]**
5. Approved outreach → send (to the local Mailpit inbox in the demo) **[core]**
6. Daily digest + weekly MPC [later]
7. Ops alerts (failure spikes, spend cap) [later]

LinkedIn and Indeed have no open applicant APIs. They connect through the firm's ATS or job-board email alerts, so never claim a direct integration.

## Data
500–1,000 synthetic resumes (PDF/DOCX) and 10–20 job orders across architecture, interior design, civil, structural, MEP and construction management. Mostly DFW, with some Houston, Austin and San Antonio. Code generates each candidate's facts and the LLM writes the resume, so **ground truth is known** for evals. Includes tricky cases: out-of-state PE, "pursuing PE"/EIT, LEED GA vs LEED AP, duplicates, odd formatting.

## Success criteria for the demo
- Runs end to end with `docker compose up`, reachable through a temporary public link with a demo login.
- Live flow: Apply → n8n → ingest → job order → match → approval → n8n sends to Mailpit, all visible in LangSmith traces.
- Eval report: extraction accuracy, match quality, evidence-grounding rate, cost per resume and per shortlist.
- Docs explain the architecture, decisions, prompts and real build problems.

## Cost
About $35–60 in total for the build and demo, nearly all Claude usage. Voyage is within its free tier, and LangSmith is on the free Developer plan.

## Roadmap (phase 2, not before the interview)
An AI CRM for the client side: account memory (RAG over emails, notes, job orders), hiring signals (job postings first, then contract awards, permits, news), relationship health, bench-to-account matching, next best action, and win/loss learning to test which signals actually lead to job orders.
Data notes: Dallas permits have no live public API (DallasNow/Accela), Austin has a daily open-data API, and USAspending shows about 40–85 new TX A/E/C federal awards a month.
