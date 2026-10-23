# 018: Conversational Ask: route messages first, keep separate conversations

- **Status:** accepted and built (owner approved 2026-10-23: "fix the chat issues"); backend measured, UI in progress
- **Date:** 2026-10-23

## Context
The Ask graph (Block 5) is a straight line: understand → retrieve → rerank → answer. In testing, the owner typed "Hey" and got a full candidate search with a list of random candidates. Expected behaviour is a greeting back, plus a prompt about what they want to do, with useful context on the day's first chat. Each question is also answered on its own: there's no memory for follow-ups like "which of those have PMP?", and history lasts only for the page visit.

The owner asked whether recruiters should have one endless chat, or chats that close when the work is done (a role is filled, profiles are submitted).

## Decision
1. **Route each message before any search.** A free keyword shortcut answers obvious one-liners ("hi", "thanks", "help"). Everything else goes to `route` (Claude Haiku 5.5, structured output, prompt `ask_route` v1, under 1 s, under $0.001), which labels the message and, in the same call, rewrites search requests and follow-ups into a standalone question:

   | Label | Example | Next step |
   |---|---|---|
   | `greeting` | "hey", "thanks" | Short reply, no search. On the day's first chat it adds context (shortlists to review, job orders with no run) and suggests next actions |
   | `help` | "what can you do?" | Capabilities with example questions |
   | `search` | "Texas PEs in DFW with drainage" | understand → retrieve → rerank → answer (today's path) |
   | `follow_up` | "which of those have PMP?" | `rewrite` into a complete question using the conversation's last candidates and filters, then search |
   | `job_order` | "who fits JO-03?" | Use that job order's structured requirements as the plan |
   | `off_topic` | "what's the weather", "list all emails" | Polite redirect, no search |

   Only `search`, `follow_up` and `job_order` run the RAG graph (`src/placewise/rag/converse.py`). A follow-up with scope "previous candidates" searches only the candidates the last answer cited; if none match, the reply says so and offers a one-click whole-pool search. If the router fails, the message is treated as a search, so a real question is never lost.

2. **Separate conversations, optionally tied to a job order.** This matches how ChatGPT and Claude work.
   - Tables `conversations` (id, user_id, title, job_order_id nullable, created_at, last_message_at) and `conversation_messages` (role, kind, content, the full answer JSON, suggestions, the candidate ids discussed, cost), migration 006. `active` is computed: a message in the last 24 h and the job order (if any) still open.
   - **Changed while building:** memory lives in `conversation_messages`, not LangGraph's Postgres checkpointer. The UI needs that table anyway to list and reopen chats, and each turn is a short graph run with no pause or resume (no `interrupt`), so a checkpointer would only store the same messages a second time. The checkpointer stays planned for the match graph's approval `interrupt`.
   - Sidebar: "New chat" plus recent conversations grouped by Today / Yesterday / Earlier, with a job-order badge. A conversation is closed automatically when its job order is filled or after 24 hours idle; closed ones stay readable, and sending a new message reopens one.
   - The job order page gets an **"Ask about this role"** button that opens a conversation tied to that job order.
   - Only the last few turns plus a short summary go back to the model, so follow-ups stay fast and cheap.

3. **Improve by measurement, not fine-tuning.**
   - About 15 test questions per message type (greetings, help, follow-ups, off-topic, injection attempts), scored in LangSmith for routing accuracy, retrieval recall and citation faithfulness.
   - 👍/👎 on each answer, linked to its LangSmith trace.
   - Outcome signal: a candidate surfaced in a conversation and later approved for submittal counts as a positive label.
   - A prompt change ships only when the test scores hold or improve.

## Measured (2026-10-23)
- Routing eval (`python -m placewise.evals.ask_routing`, 30 labeled messages incl. mixed "hi + request", follow-ups with history, job orders, off-topic and injection attempts): **30/30 correct**, $0.005.
- Live: greeting 0.02 s and $0 (keyword shortcut); off-topic 0.8–1.7 s; search ~10–12 s; job-order chat ~14 s; follow-up with no match 2.3 s (checked against the database: the 8 cited candidates top out at 9.5 years, so "none have 10+" was correct).

- **Small talk v2** (owner feedback: identical canned replies to "Hey", "How are you doing" and "sssss" felt robotic): the router (prompt `ask_route` v2) now writes a short natural reply for small talk and off-topic messages, grounded only in today's real activity (new resumes, shortlists waiting, unmatched job orders); gibberish gets "I didn't catch that"; keyword greetings rotate wording. Routing eval: **34/34**, $0.007.

## Alternatives considered
- **One endless chat per recruiter:** simplest, but filters and candidates from earlier topics leak into new questions, each follow-up resends a growing history (slower, costlier, less accurate), and there's no per-role record.
- **No memory (today):** cheap and predictable, but follow-ups fail and the page loses history on reload.
- **Keyword rules for greetings:** free and instant, but brittle ("hey, any PEs in Austin?" is a search, not a greeting). A cheap model call handles mixed messages; a keyword check can still short-circuit obvious one-word greetings.
- **Fine-tuning a model:** costly, slow to iterate, and unnecessary when the failure is routing and context rather than model knowledge.

## Tradeoffs and consequences
- **Gain:** natural greetings, working follow-ups, conversations with a record per role, and less wasted search spend.
- **Give up:** one more model call per message (about 1 s, under $0.001), a new table plus checkpoint tables, and a sidebar UI to build and test.
- **Revisit if:** routing accuracy on the test set drops below 95%, or recruiters prefer a single feed (then keep conversations but default to the latest).
