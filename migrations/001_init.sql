CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS patents (
  publication_number TEXT PRIMARY KEY,
  grant_date DATE,
  title TEXT,
  abstract TEXT,
  raw_json JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS patent_cpc (
  publication_number TEXT REFERENCES patents(publication_number) ON DELETE CASCADE,
  cpc_code TEXT NOT NULL,
  PRIMARY KEY (publication_number, cpc_code)
);

CREATE TABLE IF NOT EXISTS patent_citations (
  publication_number TEXT REFERENCES patents(publication_number) ON DELETE CASCADE,
  cited_publication_number TEXT NOT NULL,
  PRIMARY KEY (publication_number, cited_publication_number)
);

CREATE TABLE IF NOT EXISTS evidence_chunks (
  chunk_id TEXT PRIMARY KEY,
  publication_number TEXT REFERENCES patents(publication_number) ON DELETE CASCADE,
  section_type TEXT NOT NULL,
  claim_num TEXT,
  para_id TEXT,
  is_independent BOOLEAN,
  text TEXT NOT NULL,
  text_hash TEXT NOT NULL,
  metadata JSONB,
  embedding vector(768),
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chunks_pub ON evidence_chunks(publication_number);
CREATE INDEX IF NOT EXISTS idx_chunks_section ON evidence_chunks(section_type);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON evidence_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
