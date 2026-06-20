-- Fresh self-host schema for the EV Market Research RAG (v3).
-- Runs automatically on first container start (mounted into /docker-entrypoint-initdb.d).
-- The application also self-creates its chat_sessions / query_logs / ragas_scores /
-- pipeline tables at runtime (idempotent ensure_* calls), so only the core
-- retrieval table needs to exist up front.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_chunks (
    id           BIGSERIAL PRIMARY KEY,
    source       TEXT        NOT NULL,            -- google_play | app_store | news | web_pages | youtube
    app_name     TEXT        NOT NULL,
    category     TEXT        NOT NULL DEFAULT 'ev_charging',  -- ev_charging | prosumer
    content      TEXT        NOT NULL,
    metadata     JSONB       NOT NULL DEFAULT '{}',
    embedding    vector(384) NOT NULL,            -- bge-small-en-v1.5
    -- BM25 lexical search column (auto-maintained from content)
    content_tsv  tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    published_at timestamptz,                      -- news recency
    created_at   timestamptz NOT NULL DEFAULT now()
);

-- Dense ANN index (HNSW; pgvector >= 0.5). Cosine distance.
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
    ON document_chunks USING hnsw (embedding vector_cosine_ops);

-- BM25 lexical index.
CREATE INDEX IF NOT EXISTS idx_chunks_tsv
    ON document_chunks USING gin (content_tsv);

-- Filter indexes.
CREATE INDEX IF NOT EXISTS idx_chunks_app          ON document_chunks (app_name);
CREATE INDEX IF NOT EXISTS idx_chunks_source       ON document_chunks (source);
CREATE INDEX IF NOT EXISTS idx_chunks_category     ON document_chunks (category);
CREATE INDEX IF NOT EXISTS idx_chunks_published_at ON document_chunks (published_at);

-- Dedup guard used by the upsert (source + app + content).
CREATE UNIQUE INDEX IF NOT EXISTS uq_chunks_dedup
    ON document_chunks (source, app_name, md5(content));
