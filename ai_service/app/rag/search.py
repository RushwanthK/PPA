"""Try retrieval from the command line.

    python -m app.rag.search "How do I record a credit card payment?"
    python -m app.rag.search "What is UAN?" --mode keyword
    python -m app.rag.search "emergency fund" --category finance
"""

import argparse
import asyncio

import asyncpg

from ..config import get_settings
from .ingest import make_embedder
from .retrieval import retrieve


async def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("question")
    parser.add_argument("--mode", choices=["hybrid", "vector", "keyword"], default="hybrid")
    parser.add_argument("--category", choices=["ppa", "finance"])
    parser.add_argument("--top-k", type=int)
    args = parser.parse_args()

    settings = get_settings()
    embedder = make_embedder(settings)
    pool = await asyncpg.create_pool(settings.database_url.get_secret_value(), min_size=1, max_size=2)
    try:
        chunks = await retrieve(pool, embedder, args.question, top_k=args.top_k or settings.retrieval_top_k,
                                category=args.category, mode=args.mode,
                                keyword_weight=settings.keyword_weight)
    finally:
        await pool.close()
        await embedder.aclose()

    for n, c in enumerate(chunks, start=1):
        sim = f"{c.vector_similarity:.3f}" if c.vector_similarity is not None else "  -  "
        kw = c.keyword_rank if c.keyword_rank is not None else "-"
        print(f"{n}. [{c.source_path}] {c.heading}")
        print(f"   score={c.score:.4f} similarity={sim} keyword_rank={kw}")
        print("   " + c.content[:160].replace("\n", " ") + ("..." if len(c.content) > 160 else ""))


if __name__ == "__main__":
    asyncio.run(_main())
