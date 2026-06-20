-- v3 hybrid-retrieval migration (idempotent).
-- Adds BM25 lexical search support + recency column + filter indexes to the
-- existing document_chunks table. Safe to run multiple times.
--
-- Apply with:  python infrastructure/scripts/migrate_v3.py
-- (uses DATABASE_ADMIN_URL; falls back to DATABASE_URL)

CREATE EXTENSION IF NOT EXISTS vector;

-- BM25 lexical search: an indexed, auto-maintained tsvector of the content.
ALTER TABLE document_chunks
    ADD COLUMN IF NOT EXISTS content_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

CREATE INDEX IF NOT EXISTS idx_chunks_tsv
    ON document_chunks USING gin (content_tsv);

-- Recency support (news_feeds.py provides real published_at timestamps).
ALTER TABLE document_chunks
    ADD COLUMN IF NOT EXISTS published_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_chunks_published_at
    ON document_chunks (published_at);

-- Filter indexes used by app/category/source-scoped retrieval.
CREATE INDEX IF NOT EXISTS idx_chunks_app      ON document_chunks (app_name);
CREATE INDEX IF NOT EXISTS idx_chunks_source   ON document_chunks (source);
CREATE INDEX IF NOT EXISTS idx_chunks_category ON document_chunks (category);

-- OPTIONAL (requires pgvector >= 0.5): HNSW index for faster ANN search.
-- The runner executes this separately and tolerates failure on older pgvector.
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
    ON document_chunks USING hnsw (embedding vector_cosine_ops);
