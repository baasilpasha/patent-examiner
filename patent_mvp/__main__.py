from __future__ import annotations

import argparse
import json

from patent_mvp.config import SETTINGS
from patent_mvp.embeddings import SentenceTransformerProvider
from patent_mvp.ingest import run_ingest
from patent_mvp.logging_utils import configure_logging
from patent_mvp.search import hybrid_search
from patent_mvp.storage import OpenSearchStore, PostgresStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="patent_mvp")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ingest = sub.add_parser("ingest", help="Download/parse/index PTGRXML")
    ingest.add_argument("--weeks", type=int, default=12)
    ingest.add_argument("--cpc", default="G06F")
    ingest.add_argument("--since-last", action="store_true")

    search = sub.add_parser("search", help="Hybrid chunk search")
    search.add_argument("--query", required=True)
    search.add_argument("--topk", type=int, default=50)
    search.add_argument("--topk-bm25", type=int, default=200)
    search.add_argument("--topk-vec", type=int, default=200)
    search.add_argument("--graph-expand", action="store_true")
    return parser


def main() -> None:
    configure_logging()
    args = build_parser().parse_args()

    if args.cmd == "ingest":
        run_ingest(weeks=args.weeks, cpc_prefix=args.cpc, since_last=args.since_last)
        return

    if args.cmd == "search":
        pg = PostgresStore(SETTINGS.postgres_dsn)
        os_store = OpenSearchStore(SETTINGS.opensearch_url, SETTINGS.opensearch_index)
        embedder = SentenceTransformerProvider(SETTINGS.embedding_model)
        out = hybrid_search(
            query=args.query,
            embedder=embedder,
            pg=pg,
            os_store=os_store,
            topk=args.topk,
            topk_bm25=args.topk_bm25,
            topk_vec=args.topk_vec,
            graph_expand=args.graph_expand,
        )
        print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
