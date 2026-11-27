-- 0001: knowledge base for RAG (documents and their embedded chunks).
-- Requires: the vector extension and the ai schema (see db/init/001_extensions.sql).

CREATE TABLE ai.documents (
    id            bigserial PRIMARY KEY,
    source_path   text        NOT NULL UNIQUE,   -- e.g. 'ppa/02-banks.md'
    title         text        NOT NULL,
    category      text        NOT NULL CHECK (category IN ('ppa', 'finance')),
    content_hash  text        NOT NULL,          -- sha256 of the file; unchanged files are skipped
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ai.chunks (
    id              bigserial PRIMARY KEY,
    document_id     bigint      NOT NULL REFERENCES ai.documents (id) ON DELETE CASCADE,
    chunk_index     integer     NOT NULL,
    heading         text        NOT NULL,        -- 'Credit cards in PPA > Recording a payment'
    content         text        NOT NULL,
    token_estimate  integer     NOT NULL,
    content_hash    text        NOT NULL,        -- sha256 of the embedded text; lets unchanged chunks reuse embeddings
    embedding       vector(768) NOT NULL,
    embedding_model text        NOT NULL,
    -- Keyword search index text, kept up to date by Postgres itself.
    search_tsv      tsvector GENERATED ALWAYS AS (to_tsvector('english', heading || ' ' || content)) STORED,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

-- Approximate nearest-neighbour index for cosine distance (the <=> operator).
CREATE INDEX chunks_embedding_hnsw ON ai.chunks USING hnsw (embedding vector_cosine_ops);
-- Full-text (keyword) search index.
CREATE INDEX chunks_search_gin ON ai.chunks USING gin (search_tsv);
-- Embedding reuse lookups during ingestion.
CREATE INDEX chunks_content_hash ON ai.chunks (content_hash, embedding_model);
