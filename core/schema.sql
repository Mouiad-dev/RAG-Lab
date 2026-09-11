-- =============================================================================
-- core/schema.sql  —  the pgvector schema for ingested documents + chunks.
-- -----------------------------------------------------------------------------
-- Applied once at startup (idempotent: CREATE ... IF NOT EXISTS).
-- Design follows the DB rules: FK + NOT NULL + UNIQUE constraints, real indexes,
-- no stored derived data. The vector column size MUST match embeddings.dimension.
-- =============================================================================

-- pgvector must be enabled (boot_check already does this; safe to repeat).
CREATE EXTENSION IF NOT EXISTS vector;

-- ---- documents: one row per ingested file -----------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_filename TEXT        NOT NULL,
    doc_type        TEXT        NOT NULL,   -- text_pdf | image_pdf | image
    extractor_name  TEXT        NOT NULL,   -- audit: which strategy produced it
    page_count      INT         NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- same file ingested twice would create duplicate chunks; forbid it.
    CONSTRAINT uq_documents_filename UNIQUE (source_filename)
);

-- ---- chunks: many rows per document -----------------------------------------
-- NOTE: vector(1024) is hard-coupled to embeddings.dimension in rag.yaml.
-- If you change the embedder's dimension, you MUST change this column too, or
-- inserts fail LOUDLY (which is what we want — never a silent mismatch).
CREATE TABLE IF NOT EXISTS chunks (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id  BIGINT       NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index  INT          NOT NULL,
    text         TEXT         NOT NULL,
    page_number  INT          NOT NULL,     -- powers citations ("per p.4")
    embedding    vector(1024) NOT NULL,
    -- a given position within a document is unique -> safe re-ingest / upsert.
    CONSTRAINT uq_chunks_doc_index UNIQUE (document_id, chunk_index)
);

-- ---- indexes ----------------------------------------------------------------
-- FK lookups (get all chunks for a doc) should not scan.
CREATE INDEX IF NOT EXISTS ix_chunks_document_id ON chunks (document_id);

-- HNSW = fast approximate nearest-neighbour search over the vectors.
-- vector_cosine_ops because BGE-M3 vectors are normalized -> cosine similarity.
-- Without this, similarity search scans every row (fine for 100s, fatal for 1M+).
CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops);