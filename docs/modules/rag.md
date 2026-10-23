# Ask (RAG) and smart search

**Status:** Block 5, built and measured. The conversational upgrade (message routing, saved conversations, follow-ups) is designed in [ADR 018](../decisions/018-conversational-ask-routing-and-threads.md) and planned for Block 7.

The recruiter asks a question in plain English, for example "Texas PEs in DFW with drainage experience and 8+ years". Placewise answers from the resumes only, and every claim cites the resume line it came from.

## How it works today

![The Ask graph](../diagrams/rag-graph.svg)

Ask is a **RAG pipeline orchestrated with LangGraph** (`src/placewise/rag/graph.py`). Model calls go through **LangChain**, and every run is traced in **LangSmith** (project `placewise`).

| Step (LangGraph node) | What it does | Built with | Typical time |
|---|---|---|---|
| `understand` | Turns the question into a search query plus hard filters (discipline, metro, license codes, minimum years). Prompt `rag_understand` v1 | LangChain `ChatAnthropic`, **Claude Haiku 5.5**, structured output via tool calling | ~1 s |
| `retrieve` | Hybrid search over resume sections (current resume versions only, `current_chunks`). Vector search and keyword search run separately, then Reciprocal Rank Fusion (k=60) merges them | LangChain `VoyageAIEmbeddings` (**voyage-4-large**, 1024 dims), **pgvector** HNSW with iterative scan, Postgres full-text search, our own SQL | ~0.8 s |
| `rerank` | Re-scores the top 50 sections for relevance, keeps 30, groups them by candidate (up to 20 candidates, 3 sections each) and adds each candidate's credentials section | **Voyage rerank-3** | ~0.2 s |
| `answer` | Writes the answer from the retrieved sections and the code-checked profile facts only. Prompt `rag_answer` v2 | LangChain `ChatAnthropic`, **Claude Sonnet 5.5**, structured output | ~10–13 s |
| (code) | Citation check: each citation must point to a retrieved section, and its quote (at least 12 characters) must appear in that section word for word. Citations that fail are dropped and listed | Python | <10 ms |

Smart search on the Candidates page (`GET /api/search`) is the same `retrieve` + `rerank` without any LLM: about 0.5 s and no Anthropic cost.

### Why our own retrieval SQL, not LangChain's PGVector retriever
Filters, vector search and keyword search all run in one Postgres database, so every search starts with the hard filters (verified license, metro, years) and only then ranks by meaning. LangChain's `PGVector` retriever supports metadata filters on its own table layout, but not hybrid keyword + vector search with rank fusion, or filters on our typed profile columns. See [ADR 017](../decisions/017-own-retrieval-sql-over-langchain-retriever.md).

| Retrieval setup | recall@10 | precision@10 | MRR |
|---|---|---|---|
| Vector only | 48% | – | – |
| + hard filters | 84% | – | – |
| + hybrid (keyword) + rerank-3 | **89%** | **98%** | **1.00** |

Measured with `python -m placewise.evals.retrieval` on the synthetic dataset (Oct 23), using the generator's answer key, which the API never sees.

### Safety and cost
- **Untrusted input:** the question and the resume text are passed to the model as data, never as instructions. The corpus includes resumes with hidden prompt-injection text, which ingest flags as "Tampered".
- **No contact details:** email and phone are never stored in the searchable sections or in `blind_text`, so an answer can't leak them.
- **Rendering:** answers are Markdown, rendered without raw HTML, images or external links, so injected resume text can't make the browser fetch an attacker's URL.
- **Spend:** every call is logged in `llm_calls` with tokens, latency and cost, and a daily spend cap blocks new calls with a 429. One question costs about $0.03.
- **Validation:** questions must be 3–2000 characters after trimming. Filters are fixed columns with bound parameters.

## Known gap: every message runs the full search
The graph is a straight line: `understand → retrieve → rerank → answer`. A greeting like "Hey" therefore gets a full candidate search and a list of random candidates. Each question is also answered on its own, with no memory of the previous one, and the page keeps its history only for the current visit.

## Planned: conversational Ask (Block 7, ADR 018)

![Planned conversational Ask](../diagrams/ask-conversation.svg)

1. **Route each message first.** A `route` node (Haiku, under 1 s, under $0.001) labels the message as greeting, help, candidate search, follow-up, job-order question or off-topic. A LangGraph conditional edge sends only searches into retrieval. Greetings get a short reply. On the day's first chat, the reply adds useful context, such as shortlists waiting for review or job orders with no run yet.
2. **Separate conversations**, optionally tied to a job order, instead of one endless chat. Conversations close when the job order is filled or after 24 hours idle, and stay readable.
3. **Follow-ups with memory.** Conversation state is saved with LangGraph's Postgres checkpointer. A `rewrite` node turns "which of them have PMP?" into a complete question that keeps the previous candidates and filters.
4. **Improve with measurements, not fine-tuning:** test questions for each message type in LangSmith, 👍/👎 feedback, and outcome signals (a candidate surfaced in a conversation and later approved). Prompt changes ship only when the test scores hold or improve.

## Files
- `src/placewise/rag/graph.py`: the LangGraph and its nodes
- `src/placewise/rag/retrieve.py`: filters, vector search, keyword search, RRF, grouping
- `src/placewise/rag/rerank.py`: Voyage rerank-3
- `src/placewise/rag/answer.py`: understand and answer prompts, citation check, costs
- `src/placewise/rag_api.py`: `POST /api/ask`, `GET /api/search`
- `src/placewise/evals/retrieval.py`: retrieval evaluation
- `prompts/rag_understand.v1.md`, `prompts/rag_answer.v2.md`
- `web/src/app/(app)/ask/ask-view.tsx`: the Ask page
