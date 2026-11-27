"""Retrieval evaluation: does the right document come back for known questions?

    python -m app.rag.evaluate             all three modes, real Gemini embeddings
    python -m app.rag.evaluate --misses    also list the questions each mode got wrong

Metrics (per question, the "hit" is the first retrieved chunk from an expected document):
- hit@1: the top result is from an expected document
- hit@k: an expected document is anywhere in the top k
- MRR (mean reciprocal rank): average of 1 / position of the first hit (0 if none)

Token control: all questions are embedded in ONE batched API call and the vectors are
reused for every mode, so a full evaluation costs a single embedding request.
"""

import argparse
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

import asyncpg

from ..config import SERVICE_DIR, get_settings
from .embeddings import Embedder
from .ingest import make_embedder
from .retrieval import Mode, retrieve

EVAL_FILE = SERVICE_DIR / "eval" / "retrieval_set.jsonl"


@dataclass(frozen=True)
class EvalCase:
    question: str
    expected: tuple[str, ...]


@dataclass
class ModeResult:
    mode: str
    hit_at_1: float
    hit_at_k: float
    mrr: float
    misses: list[dict]


def load_cases(path: Path = EVAL_FILE) -> list[EvalCase]:
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            cases.append(EvalCase(row["question"], tuple(row["expected"])))
    return cases


def first_hit_position(retrieved_sources: list[str], expected: tuple[str, ...]) -> int | None:
    for position, source in enumerate(retrieved_sources, start=1):
        if source in expected:
            return position
    return None


def score(positions: list[int | None]) -> tuple[float, float, float]:
    n = len(positions) or 1
    hit1 = sum(1 for p in positions if p == 1) / n
    hitk = sum(1 for p in positions if p is not None) / n
    mrr = sum(1 / p for p in positions if p is not None) / n
    return hit1, hitk, mrr


async def evaluate(pool: asyncpg.Pool, embedder: Embedder, cases: list[EvalCase], *,
                   modes: tuple[Mode, ...] = ("vector", "keyword", "hybrid"), top_k: int = 5,
                   keyword_weight: float = 1.0) -> list[ModeResult]:
    needs_vectors = any(m != "keyword" for m in modes)
    vectors = await embedder.embed_queries([c.question for c in cases]) if needs_vectors else []
    results = []
    for mode in modes:
        positions, misses = [], []
        for i, case in enumerate(cases):
            chunks = await retrieve(pool, embedder, case.question, top_k=top_k, mode=mode,
                                    query_vector=vectors[i] if vectors else None,
                                    keyword_weight=keyword_weight)
            sources = [c.source_path for c in chunks]
            pos = first_hit_position(sources, case.expected)
            positions.append(pos)
            if pos != 1:
                misses.append({"question": case.question, "expected": list(case.expected),
                               "got": sources[:3], "position": pos})
        hit1, hitk, mrr = score(positions)
        results.append(ModeResult(mode, hit1, hitk, mrr, misses))
    return results


async def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--misses", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    embedder = make_embedder(settings)
    pool = await asyncpg.create_pool(settings.database_url.get_secret_value(), min_size=1, max_size=4)
    try:
        cases = load_cases()
        results = await evaluate(pool, embedder, cases, top_k=settings.retrieval_top_k,
                                 keyword_weight=settings.keyword_weight)
    finally:
        await pool.close()
        await embedder.aclose()

    k = settings.retrieval_top_k
    print(f"{len(cases)} questions, top_k={k}, keyword_weight={settings.keyword_weight}, "
          f"embedding model={embedder.model}")
    print(f"{'mode':8} {'hit@1':>6} {'hit@' + str(k):>6} {'MRR':>6}")
    for r in results:
        print(f"{r.mode:8} {r.hit_at_1:6.2f} {r.hit_at_k:6.2f} {r.mrr:6.2f}")
    print(f"embedding API requests: {embedder.usage.requests}")
    if args.misses:
        for r in results:
            print(f"\n--- {r.mode}: not ranked first ---")
            for m in r.misses:
                print(json.dumps(m))


if __name__ == "__main__":
    asyncio.run(_main())
