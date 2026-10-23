-- 006: saved Ask conversations (Block 7, ADR 018). Each user sees only their own.
-- A conversation can be tied to a job order ("Ask about this role"). Messages keep the full answer
-- (citations, candidates, plan) so a chat can be reopened, and follow-ups can reuse the last candidates.
CREATE TABLE conversations (
    id               BIGSERIAL PRIMARY KEY,
    user_id          BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    title            TEXT NOT NULL DEFAULT 'New chat',
    job_order_id     BIGINT REFERENCES job_orders (id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_message_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX conversations_user_idx ON conversations (user_id, last_message_at DESC);

CREATE TABLE conversation_messages (
    id               BIGSERIAL PRIMARY KEY,
    conversation_id  BIGINT NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
    role             TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    kind             TEXT NOT NULL,          -- user | greeting | help | off_topic | intro | search | follow_up | job_order
    content          TEXT NOT NULL,
    response         JSONB,                  -- the full RAG result for search kinds
    suggestions      TEXT[] NOT NULL DEFAULT '{}',
    person_ids       BIGINT[] NOT NULL DEFAULT '{}',   -- candidates shown, for follow-ups ("which of those...")
    cost_usd         NUMERIC(10, 6) NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX conversation_messages_conv_idx ON conversation_messages (conversation_id, id);
