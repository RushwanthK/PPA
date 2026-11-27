"""Hybrid retrieval: vector (semantic) search + keyword (full-text) search, fused with RRF.

Why both:
- Vector search finds meaning even with different words ("pay my card bill" finds
  "Recording a payment").
- Keyword search is reliable for exact terms such as "EPF", "UAN", "DICGC" or
  "Process billing", where embeddings can be vague.

Reciprocal Rank Fusion (RRF) merges the two ranked lists using only positions
(score = sum of 1 / (k + rank)), so the very different score scales of cosine
distance and ts_rank never need to be compared.

Concurrency: the keyword search does not need the query embedding, so it runs at
the same time as "embed query, then vector search" (asyncio.gather on two pool
connections). Total latency is roughly the slower of the two, not their sum.
"""

import asyncio
from dataclasses import dataclass
from typing import Literal

import asyncpg

from .embeddings import Embedder, vector_literal

RRF_K = 60
Mode = Literal["hybrid", "vector", "keyword"]


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    source_path: str
    title: str
    category: str
    heading: str
    content: str
    score: float                      # fused RRF score (or the single method's score)
    vector_similarity: float | None   # cosine similarity 0..1; None if not found by vector search
    keyword_rank: int | None          # 1-based position in the keyword results


_SELECT = """
    SELECT c.id, d.source_path, d.title, d.category, c.heading, c.content{extra}
    FROM ai.chunks c JOIN ai.documents d ON d.id = c.document_id
"""


async def _vector_search(pool: asyncpg.Pool, embedder: Embedder, query: str, limit: int,
                         category: str | None, query_vector: list[float] | None) -> list[asyncpg.Record]:
    if query_vector is None:
        query_vector = (await embedder.embed_queries([query]))[0]
    async with pool.acquire() as conn:
        return await conn.fetch(
            _SELECT.format(extra=", 1 - (c.embedding <=> $1::vector) AS similarity")
            + " WHERE ($3::text IS NULL OR d.category = $3)"
            + " ORDER BY c.embedding <=> $1::vector LIMIT $2",
            vector_literal(query_vector), limit, category,
        )


async def _keyword_search(pool: asyncpg.Pool, query: str, limit: int, category: str | None) -> list[asyncpg.Record]:
    async with pool.acquire() as conn:
        # websearch_to_tsquery ANDs all words, which is too strict for questions.
        # Rebuild it as OR so any matching keyword counts; ts_rank_cd rewards more matches.
        return await conn.fetch(
            _SELECT.format(extra=", ts_rank_cd(c.search_tsv, q) AS rank")
            + """
            , to_tsquery('simple', replace(websearch_to_tsquery('english', $1)::text, ' & ', ' | ')) AS q
            WHERE c.search_tsv @@ q AND ($3::text IS NULL OR d.category = $3)
            ORDER BY rank DESC, c.id LIMIT $2
            """,
            query, limit, category,
        )


def reciprocal_rank_fusion(*rankings: list[int], weights: tuple[float, ...] | None = None,
                           k: int = RRF_K) -> dict[int, float]:
    """Each ranking is a list of ids, best first. Returns id -> fused score.
    Optional weights scale each ranking's contribution (weighted RRF)."""
    weights = weights or (1.0,) * len(rankings)
    scores: dict[int, float] = {}
    for ranking, weight in zip(rankings, weights):
        for position, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + weight / (k + position)
    return scores


async def retrieve(
    pool: asyncpg.Pool,
    embedder: Embedder,
    query: str,
    *,
    top_k: int = 5,
    candidates: int = 20,
    category: str | None = None,
    mode: Mode = "hybrid",
    query_vector: list[float] | None = None,
    keyword_weight: float = 1.0,
) -> list[RetrievedChunk]:
    query = query.strip()
    if not query:
        return []

    vector_rows: list[asyncpg.Record] = []
    keyword_rows: list[asyncpg.Record] = []
    if mode == "hybrid":
        vector_rows, keyword_rows = await asyncio.gather(
            _vector_search(pool, embedder, query, candidates, category, query_vector),
            _keyword_search(pool, query, candidates, category),
        )
    elif mode == "vector":
        vector_rows = await _vector_search(pool, embedder, query, candidates, category, query_vector)
    else:
        keyword_rows = await _keyword_search(pool, query, candidates, category)

    rows = {r["id"]: r for r in [*keyword_rows, *vector_rows]}
    similarity = {r["id"]: float(r["similarity"]) for r in vector_rows}
    keyword_position = {r["id"]: i for i, r in enumerate(keyword_rows, start=1)}

    if mode == "hybrid":
        scores = reciprocal_rank_fusion([r["id"] for r in vector_rows], [r["id"] for r in keyword_rows],
                                        weights=(1.0, keyword_weight))
    elif mode == "vector":
        scores = similarity
    else:
        scores = {r["id"]: float(r["rank"]) for r in keyword_rows}

    ranked = sorted(scores, key=lambda i: (-scores[i], i))[:top_k]
    return [
        RetrievedChunk(
            chunk_id=i,
            source_path=rows[i]["source_path"],
            title=rows[i]["title"],
            category=rows[i]["category"],
            heading=rows[i]["heading"],
            content=rows[i]["content"],
            score=scores[i],
            vector_similarity=similarity.get(i),
            keyword_rank=keyword_position.get(i),
        )
        for i in ranked
    ]
