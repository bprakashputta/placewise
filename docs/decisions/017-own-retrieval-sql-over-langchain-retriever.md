# 017: Our own retrieval SQL instead of LangChain's PGVector retriever

- **Status:** accepted
- **Date:** 2026-10-23

## Context
Ask and matching need to retrieve resume sections that meet hard requirements (an active Texas PE, DFW, 8+ years) and are relevant to a free-text need ("drainage, HEC-RAS"). Measured on the synthetic dataset, vector search alone found only 48% of the right candidates in the top 10. Most misses were candidates who read similarly but lacked the required license or location.

## Decision
Keep LangChain for model and embedding calls (`ChatAnthropic`, `VoyageAIEmbeddings`) and LangGraph for orchestration. Write retrieval as **our own SQL over Postgres + pgvector** (`src/placewise/rag/retrieve.py`):
1. Hard filters on typed, code-validated profile columns (`license_codes`, `metro`, `years_experience`, `discipline`), with bound parameters.
2. A vector search (HNSW, `hnsw.iterative_scan = relaxed_order`, so filtered queries still return enough rows) and a full-text keyword search, each over current resume versions only.
3. Reciprocal Rank Fusion (k=60), then Voyage rerank-3, then grouping by candidate.

## Alternatives considered
- **LangChain `PGVector` retriever:** quick to set up, but it uses its own table layout with JSON metadata filters, has no keyword search or rank fusion, and can't filter on our typed columns and GIN indexes.
- **LangChain `EnsembleRetriever` (vector + BM25):** does fusion, but BM25 runs in memory over the whole corpus, outside the database, and the filters don't carry through cleanly.
- **A separate vector database (Pinecone, Qdrant):** filters and profile facts would live in two systems that must stay in sync. See ADR 001.

## Tradeoffs and consequences
- **Gain:** recall@10 went from 48% to 89% (precision@10 98%, MRR 1.0). Filters, search and facts sit in one transactional store, and retrieval is plain SQL we can test and explain.
- **Give up:** LangChain's retriever interface. We maintain about 150 lines of SQL and fusion code, and swapping vector stores later means rewriting it.
- **Revisit if:** the corpus outgrows one Postgres instance (millions of sections), or LangChain gains hybrid search with typed filters on Postgres.
