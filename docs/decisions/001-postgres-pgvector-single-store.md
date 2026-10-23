# 001: Postgres + pgvector as the single data store

- **Status:** accepted
- **Date:** 2026-10-22

## Context
Placewise needs structured data (candidates, job orders, users, approvals), vector search over resume chunks, keyword search, a job queue for the worker, and LangGraph checkpoints. It's a demo built by one person in a week, run with `docker compose up`, with roughly 500–1,000 synthetic resumes.

## Decision
Use one Postgres 17 database with the pgvector extension (`pgvector/pgvector:0.8.1-pg17`) for everything:
- structured tables,
- vectors (pgvector HNSW),
- full-text search (Postgres `tsvector`),
- the job queue (`SELECT … FOR UPDATE SKIP LOCKED`),
- LangGraph checkpoints (Postgres checkpointer).

Block 0 creates the extension (`docker/db/init/001-extensions.sql`) and `/api/health` verifies it is installed. Tables and migrations come in Block 2.

## Alternatives considered
- **Pinecone / Weaviate / Qdrant + Postgres:** better at very large vector scale and managed ops, but adds a second store to keep in sync (deletes, updates, blind copies), a second set of credentials, and makes "hard SQL filters + vector + full-text in one query" a cross-service join. Pinecone is also not runnable locally in Compose.
- **Redis or RabbitMQ for the queue:** another service to run and monitor; at this volume, a `SKIP LOCKED` table is enough and is transactional with the data it processes.
- **SQLite + a vector extension:** simpler, but a single writer is a poor fit for an api plus horizontally scaled workers, and `SKIP LOCKED` queues need Postgres.

## Tradeoffs and consequences
- **Gain:** one backup, one connection pool, transactional consistency between a candidate, its chunks and its queue job; hybrid retrieval (filters → vector + full-text → RRF) in SQL.
- **Give up:** pgvector's HNSW is slower and uses more memory than dedicated engines at millions of vectors; one database is a single point of failure and a shared load.
- **Revisit if:** the corpus grows to millions of chunks, vector query latency becomes the bottleneck, or queue throughput contends with app queries.
