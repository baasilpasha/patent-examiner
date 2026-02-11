CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS ingestion_state (
    source TEXT PRIMARY KEY,
    last_week TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS patents (
    publication_number TEXT PRIMARY KEY,
    grant_date DATE,
    title TEXT,
    abstract_text TEXT,
    summary_text TEXT,
    description_text TEXT,
    raw_json JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    publication_number TEXT NOT NULL REFERENCES patents(publication_number) ON DELETE CASCADE,
    section_type TEXT NOT NULL,
    claim_num TEXT,
    para_id TEXT,
    is_dependent BOOLEAN,
    text TEXT NOT NULL,
    text_hash TEXT NOT NULL,
    embedding vector(768),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_chunks_pub ON chunks(publication_number);
CREATE INDEX IF NOT EXISTS idx_chunks_section ON chunks(section_type);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE TABLE IF NOT EXISTS patent_citations (
    citing_publication TEXT NOT NULL REFERENCES patents(publication_number) ON DELETE CASCADE,
    cited_publication TEXT NOT NULL,
    PRIMARY KEY (citing_publication, cited_publication)
);

CREATE TABLE IF NOT EXISTS patent_cpc (
    publication_number TEXT NOT NULL REFERENCES patents(publication_number) ON DELETE CASCADE,
    cpc_code TEXT NOT NULL,
    PRIMARY KEY (publication_number, cpc_code)
);

CREATE INDEX IF NOT EXISTS idx_patent_cpc_code ON patent_cpc(cpc_code);
