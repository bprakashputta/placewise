# 018: Conversational Ask: route messages first, keep separate conversations

- **Status:** proposed (Block 7, awaiting owner approval to build)
- **Date:** 2026-10-23

## Context
The Ask graph (Block 5) is a straight line: understand → retrieve → rerank → answer. In testing, the owner typed "Hey" and got a full candidate search with a list of random candidates. Expected behaviour is a greeting back, plus a prompt about what they want to do, with useful context on the day's first chat. Each question is also answered on its own: there's no memory for follow-ups like "which of those have PMP?", and history lasts only for the page visit.

The owner asked whether recruiters should have one endless chat, or chats that close when the work is done (a role is filled, profiles are submitted).

## Decision
1. **Route each message before any search.** A new first LangGraph node, `route` (Claude Haiku 5.5, structured output, under 1 s, under $0.001), labels each message:

   | Label | Example | Next step |
   |---|---|---|
   | `greeting` | "hey", "thanks" | Short reply, no search. On the day's first chat it adds context (shortlists to review, job orders with no run) and suggests next actions |
   | `help` | "what can you do?" | Capabilities with example questions |
   | `search` | "Texas PEs in DFW with drainage" | understand → retrieve → rerank → answer (today's path) |
   | `follow_up` | "which of those have PMP?" | `rewrite` into a complete question using the conversation's last candidates and filters, then search |
   | `job_order` | "who fits JO-03?" | Use that job order's structured requirements as the plan |
   | `off_topic` | "what's the weather", "list all emails" | Polite redirect, no search |

   A LangGraph conditional edge (`add_conditional_edges`) sends only `search`, `follow_up` and `job_order` into retrieval.

2. **Separate conversations, optionally tied to a job order.** This matches how ChatGPT and Claude work.
   - New table `conversations` (id, user_id, title, job_order_id nullable, status active|closed, created_at, last_message_at). Messages and graph state are stored by LangGraph's **Postgres checkpointer**, keyed by conversation id.
   - Sidebar: "New chat" plus recent conversations grouped by Today / Yesterday / Earlier, with a job-order badge. A conversation is closed automatically when its job order is filled or after 24 hours idle; closed ones stay readable, and sending a new message reopens one.
   - The job order page gets an **"Ask about this role"** button that opens a conversation tied to that job order.
   - Only the last few turns plus a short summary go back to the model, so follow-ups stay fast and cheap.

3. **Improve by measurement, not fine-tuning.**
   - About 15 test questions per message type (greetings, help, follow-ups, off-topic, injection attempts), scored in LangSmith for routing accuracy, retrieval recall and citation faithfulness.
   - 👍/👎 on each answer, linked to its LangSmith trace.
   - Outcome signal: a candidate surfaced in a conversation and later approved for submittal counts as a positive label.
   - A prompt change ships only when the test scores hold or improve.

## Alternatives considered
- **One endless chat per recruiter:** simplest, but filters and candidates from earlier topics leak into new questions, each follow-up resends a growing history (slower, costlier, less accurate), and there's no per-role record.
- **No memory (today):** cheap and predictable, but follow-ups fail and the page loses history on reload.
- **Keyword rules for greetings:** free and instant, but brittle ("hey, any PEs in Austin?" is a search, not a greeting). A cheap model call handles mixed messages; a keyword check can still short-circuit obvious one-word greetings.
- **Fine-tuning a model:** costly, slow to iterate, and unnecessary when the failure is routing and context rather than model knowledge.

## Tradeoffs and consequences
- **Gain:** natural greetings, working follow-ups, conversations with a record per role, and less wasted search spend.
- **Give up:** one more model call per message (about 1 s, under $0.001), a new table plus checkpoint tables, and a sidebar UI to build and test.
- **Revisit if:** routing accuracy on the test set drops below 95%, or recruiters prefer a single feed (then keep conversations but default to the latest).
