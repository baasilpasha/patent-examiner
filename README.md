# Patent Retrieval Layer MVP

Local-first hybrid retrieval stack for US granted patents (PTGRXML), filtered to CPC `G06F`, with chunk-level evidence search and patent-level ranking.

## What this builds

- Downloader that discovers **latest N PTGRXML weekly grant files dynamically** (default 12) through the **USPTO Open Data Portal (ODP) bulk-data search API**.
- Resumable/idempotent weekly downloads (`.part` + HTTP range) with processed-week state tracking.
- Parser for PTGRXML grant XML using namespace-tolerant XPath over multiple structure variants.
- G06F filter (`keep patent if any CPC starts with G06F`).
- Evidence chunking:
  - claim-per-chunk (with claim number + independent/dependent heuristic),
  - one abstract chunk,
  - summary and description paragraph chunks split to `<=1200` chars with `150` overlap.
- Storage:
  - Postgres (+ pgvector) is source of truth.
  - OpenSearch for BM25 + snippets.
  - Citation and CPC edges in Postgres for graph expansion.
- Embeddings:
  - local sentence-transformers with CUDA auto-detection and CPU fallback,
  - hash-based embedding cache so chunks are not re-embedded unnecessarily,
  - enforced vector dimension compatibility with schema (`vector(768)`).
- Hybrid retrieval:
  - BM25 top-K + vector top-K, weighted merge/dedupe,
  - optional graph expansion via citations + CPC neighbors.

## Repository layout

- `patent_mvp/`: Python package and CLI
- `migrations/001_init.sql`: Postgres schema
- `docker-compose.yml`: Postgres + OpenSearch
- `tests/`: unit + fixture smoke tests
- `data/`: runtime-only storage (**gitignored**)

Runtime paths used:

- Raw weekly downloads: `data/raw/ptgrxml/ipgYYYYMMDD/`
- Parsed patent JSON: `data/parsed/patents/`
- Chunk JSONL by week: `data/derived/chunks/ipgYYYYMMDD.jsonl`

## Prerequisites on Fedora server

- Docker + Docker Compose plugin
- Python 3.10+
- Optional CUDA drivers/runtime for GPU embedding acceleration

## Setup

```bash
git clone <your-repo-url>
cd patent-examiner

python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .[dev]

docker compose up -d
```

## Environment variables

- `ODP_BULK_SEARCH_URL` (optional): ODP bulk-data search API URL.
  - default: `https://api.uspto.gov/api/v1/bulk-data/search`
- `ODP_API_KEY` (optional): API key header value if your ODP deployment requires one.
- `EMBEDDING_MODEL` (optional): sentence-transformers model name.
  - default: `BAAI/bge-base-en-v1.5` (**768 dimensions**, compatible with current pgvector schema).

## CLI

### Ingest latest weeks

```bash
python -m patent_mvp ingest --weeks 12 --cpc G06F
```

### Incremental ingest (only new discovered weeks)

```bash
python -m patent_mvp ingest --since-last
```

### Hybrid search

```bash
python -m patent_mvp search --query "A computer-implemented method comprising scheduling tasks across GPU and CPU" --topk 50
```

With graph expansion:

```bash
python -m patent_mvp search --query "A computer-implemented method comprising scheduling tasks across GPU and CPU" --topk 50 --graph-expand
```

## ODP discovery and debug logging

Ingest logs include selected week ids and resolved download URLs, e.g. tuples like:

```text
('20240213', 'https://.../ipg20240213.zip')
```

This helps verify exactly which ODP files were selected and downloaded.

## Embedding dimension safety

Current DB schema stores embeddings as `vector(768)`. At runtime, the embedding provider validates output dimension:

- if model outputs `768`, ingest/search continue;
- otherwise, code fails fast with a clear error instructing you to:
  1. switch to a 768-d model via `EMBEDDING_MODEL`, or
  2. run a DB migration to change vector dimension.

## Weekly update behavior

- Downloader queries ODP API for PTGRXML bulk files sorted newest-first.
- Processed weeks are recorded under `data/raw/ptgrxml/processed_weeks.json`.
- `--since-last` only downloads/parses newly discovered weeks not already marked processed.
- Downloads are resumable (`.part` temp files + HTTP range support).

## Scale path (12 weeks -> full corpus)

1. Increase `--weeks` and run batch-by-batch.
2. Add OpenSearch shard/replica tuning and larger JVM heap.
3. Rebuild pgvector indexes for higher list counts and tune autovacuum.
4. Add queue-based distributed embedding workers if GPU saturation occurs.
5. Add secondary embedding spaces (e.g., PatentBERT) via `EmbeddingProvider` abstraction.

## Testing

CI-safe tests are fixture/small-unit only (no large downloads/indexing):

```bash
pytest -q
```

## Fedora runbook commands

### Smoke ingest: 1 week

```bash
docker compose up -d
source .venv/bin/activate
python -m patent_mvp ingest --weeks 1 --cpc G06F
```

### Medium ingest: 12 weeks

```bash
docker compose up -d
source .venv/bin/activate
python -m patent_mvp ingest --weeks 12 --cpc G06F
```

### Incremental weekly update

```bash
python -m patent_mvp ingest --since-last
```

### Search

```bash
python -m patent_mvp search --query "1. A system comprising a processor configured to allocate memory pages based on workload priority" --topk 50
python -m patent_mvp search --query "1. A system comprising a processor configured to allocate memory pages based on workload priority" --topk 50 --graph-expand
```

## Notes for cloud PR workflow

This repo is designed so CI only runs unit/fixture smoke tests. Large PTGRXML downloads, full indexing, and heavy embedding should be run on your remote Fedora server.
