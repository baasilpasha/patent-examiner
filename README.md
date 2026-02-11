# Patent Retrieval Layer MVP (`patent_mvp`)

A modular, fully-local retrieval layer for US granted patents (PTGRXML) filtered to CPC `G06F`, with hybrid retrieval:

- **BM25 keyword retrieval** in OpenSearch over evidence chunks.
- **Semantic vector retrieval** in Postgres + pgvector.
- **Optional graph expansion** over citation edges + CPC neighbors.

> Designed for runtime execution on a remote Fedora server with optional CUDA acceleration. This repo intentionally avoids large downloads/index builds in CI or dev cloud runs.

## What this MVP implements

- PTGRXML weekly discovery (newest N weeks chosen dynamically, no hardcoded dates).
- Resumable/idempotent weekly ZIP download.
- Incremental updates via `--since-last` tracking in Postgres.
- CPC filter: keep a patent if any CPC code starts with `G06F` (or provided prefix).
- Evidence chunking:
  - CLAIM: one chunk per claim + dependency metadata.
  - ABSTRACT: one chunk.
  - SUMMARY / DESCRIPTION: paragraph chunks, split to <=1200 chars with 150-char overlap.
- Safe text normalization (NFKC, whitespace/entity cleanup, conservative wrapped-hyphen fix).
- Stable `chunk_id` hashing scheme.
- Storage of citations and CPC edges in Postgres.
- Embedding abstraction with default SentenceTransformer model and hash-based embedding cache.
- Unit tests + fixture smoke parse/chunk test.

## Server prerequisites (Fedora)

- Docker + Docker Compose plugin
- Python 3.10+
- (Optional) NVIDIA drivers + CUDA runtime for GPU embeddings

Install quick-start (example):

```bash
sudo dnf install -y git python3.11 python3.11-pip docker docker-compose-plugin
sudo systemctl enable --now docker
```

## Local services (Postgres + OpenSearch)

```bash
docker compose up -d
```

Services:
- Postgres (`pgvector`): `localhost:5432`
- OpenSearch: `localhost:9200`

## Python setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .[dev]
```

## CLI

### Ingest newest 12 weeks (default)

```bash
python -m patent_mvp ingest --weeks 12 --cpc G06F
```

### Incremental ingest since last processed week

```bash
python -m patent_mvp ingest --since-last --cpc G06F
```

### Hybrid search

```bash
python -m patent_mvp search --query "A computer-implemented method comprising receiving user input..." --topk 50
```

With graph expansion:

```bash
python -m patent_mvp search --query "..." --topk 50 --graph-expand
```

## Data layout on server

- Raw weekly downloads: `data/raw/ptgrxml/ipgYYYYMMDD/`
- Parsed patent JSON: `data/parsed/patents/`
- Chunk JSONL by week: `data/derived/chunks/ipgYYYYMMDD.jsonl`
- Embedding hash cache: `data/derived/embedding_cache.json`

`data/` is gitignored.

## Default embedding model

- `sentence-transformers/all-mpnet-base-v2`
  - Strong baseline for semantic retrieval.
  - Automatically uses CUDA when available; CPU fallback otherwise.

Override via env var:

```bash
export EMBEDDING_MODEL="sentence-transformers/all-mpnet-base-v2"
```

## Weekly update workflow

1. `ingest --since-last` checks `ingestion_state` in Postgres.
2. Downloader lists current PTGRXML weekly files and selects only weeks newer than `last_week`.
3. Only new weeks are downloaded/parsed/chunked/indexed.
4. `last_week` is updated after successful week processing.

## Scale path (12 weeks -> larger corpus)

- Increase `--weeks` or run repeated incremental updates.
- Tune OpenSearch and Postgres resources in `docker-compose.yml` for larger corpora.
- Add partitioning for chunk tables and async/bulk indexing.
- Switch/augment embedding providers through `EmbeddingProvider` abstraction.
- Extend graph rerank and add future reranking/verifier steps.

## Testing

Run lightweight tests only (no large downloads):

```bash
pytest
```

## Fedora server run commands requested

Smoke ingest (1 week):

```bash
python -m patent_mvp ingest --weeks 1 --cpc G06F
```

Medium ingest (12 weeks):

```bash
python -m patent_mvp ingest --weeks 12 --cpc G06F
```

Search:

```bash
python -m patent_mvp search --query "A system comprising a processor configured to classify network traffic and update a model." --topk 50 --graph-expand
```

## Notes for future extensions

The code is intentionally modular to support:

- Limitation-level indexing
- Reranker/verifier integration
- Full claim-chart mapping
- Additional corpora (papers/standards)
