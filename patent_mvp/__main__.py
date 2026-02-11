from __future__ import annotations

import argparse
import json
import logging

from patent_mvp.config import Settings
from patent_mvp.db import PostgresStore
from patent_mvp.embeddings import SentenceTransformerProvider
from patent_mvp.ingest import run_ingest
from patent_mvp.retrieval import run_search
from patent_mvp.search_index import OpenSearchStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="patent_mvp")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Download/process USPTO PTGRXML grants")
    ingest.add_argument("--weeks", type=int, default=12)
    ingest.add_argument("--cpc", type=str, default="G06F")
    ingest.add_argument("--since-last", action="store_true")

    search = sub.add_parser("search", help="Hybrid patent evidence search")
    search.add_argument("--query", required=True)
    search.add_argument("--topk", type=int, default=50)
    search.add_argument("--topk-bm25", type=int, default=200)
    search.add_argument("--topk-vec", type=int, default=200)
    search.add_argument("--graph-expand", action="store_true")
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = build_parser()
    args = parser.parse_args()
    settings = Settings()

    if args.command == "ingest":
        run_ingest(settings=settings, weeks=args.weeks, cpc_prefix=args.cpc, since_last=args.since_last)
        return

    if args.command == "search":
        db = PostgresStore(settings.postgres_dsn)
        index = OpenSearchStore(settings.opensearch_url, settings.opensearch_index)
        embedder = SentenceTransformerProvider(
            model_name=settings.embedding_model,
            cache_path=settings.data_root / "derived" / "embedding_cache.json",
            batch_size=settings.batch_size,
        )
        result = run_search(
            query=args.query,
            topk=args.topk,
            topk_bm25=args.topk_bm25,
            topk_vec=args.topk_vec,
            graph_expand=args.graph_expand,
            db=db,
            index=index,
            embedder=embedder,
        )
        print(json.dumps({"chunks": result.chunks, "patents": result.patents}, indent=2))


if __name__ == "__main__":
    main()
