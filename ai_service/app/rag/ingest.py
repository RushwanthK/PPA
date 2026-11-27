"""Load the knowledge folder into the database: chunk, embed, store.

    python -m app.rag.ingest            ingest changes (calls the embedding API only for new text)
    python -m app.rag.ingest --dry-run  show what would change and the estimated tokens, without API calls or writes

Token control:
- Unchanged files are skipped entirely (file hash).
- In a changed file, chunks whose text did not change reuse their stored
  embedding (chunk hash), so editing one paragraph re-embeds about one chunk.
- Changing the embedding model re-embeds everything, because vectors from
  different models cannot be compared.
"""

import argparse
import asyncio
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

import asyncpg

from ..config import Settings, get_settings
from .chunking import Chunk, chunk_document, sha256
from .embeddings import Embedder, GeminiEmbedder, vector_literal

log = logging.getLogger("ppa_ai.ingest")

CATEGORIES = {"ppa", "finance"}


@dataclass
class IngestReport:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    chunks_written: int = 0
    chunks_embedded: int = 0   # new embeddings requested from the API
    chunks_reused: int = 0     # embeddings copied from unchanged chunks
    estimated_tokens_embedded: int = 0


@dataclass
class SourceFile:
    source_path: str  # relative, forward slashes: 'ppa/02-banks.md'
    category: str
    text: str

    @property
    def file_hash(self) -> str:
        return sha256(self.text)


def discover(knowledge_dir: Path) -> list[SourceFile]:
    files = []
    for path in sorted(knowledge_dir.rglob("*.md")):
        rel = path.relative_to(knowledge_dir).as_posix()
        category = rel.split("/", 1)[0]
        if category not in CATEGORIES:
            log.warning("Skipping %s: folder must be one of %s", rel, sorted(CATEGORIES))
            continue
        files.append(SourceFile(rel, category, path.read_text(encoding="utf-8")))
    return files


async def ingest(
    pool: asyncpg.Pool,
    embedder: Embedder,
    knowledge_dir: Path,
    *,
    max_tokens: int = 350,
    overlap_tokens: int = 60,
    dry_run: bool = False,
) -> IngestReport:
    report = IngestReport()
    sources = discover(knowledge_dir)

    async with pool.acquire() as conn:
        existing = {
            r["source_path"]: r for r in await conn.fetch(
                """
                SELECT d.id, d.source_path, d.content_hash,
                       bool_and(c.embedding_model = $1) AS same_model
                FROM ai.documents d LEFT JOIN ai.chunks c ON c.document_id = d.id
                GROUP BY d.id
                """,
                embedder.model,
            )
        }

        # Pass 1: find changed documents and the chunks that need new embeddings.
        changed = []  # (source, parsed doc, chunks)
        reusable: dict[str, str] = {}
        to_embed: dict[str, Chunk] = {}  # content_hash -> chunk (identical text embedded once)
        for src in sources:
            row = existing.get(src.source_path)
            if row and row["content_hash"] == src.file_hash and row["same_model"] is not False:
                report.unchanged.append(src.source_path)
                continue
            doc, chunks = chunk_document(src.text, max_tokens=max_tokens, overlap_tokens=overlap_tokens)
            reusable.update(await _reusable_embeddings(conn, chunks, embedder.model))
            for c in chunks:
                if c.content_hash in reusable:
                    report.chunks_reused += 1
                elif c.content_hash not in to_embed:
                    to_embed[c.content_hash] = c
            (report.updated if row else report.added).append(src.source_path)
            changed.append((src, doc, chunks))
        report.chunks_embedded = len(to_embed)
        report.estimated_tokens_embedded = sum(c.token_estimate for c in to_embed.values())

        # Pass 2: one batched embedding call across ALL changed documents
        # (fewer requests than one call per document).
        new_vectors: dict[str, str] = {}
        if to_embed and not dry_run:
            pending = list(to_embed.values())
            vectors = await embedder.embed_documents([c.embedding_text for c in pending])
            new_vectors = {c.content_hash: vector_literal(v) for c, v in zip(pending, vectors)}

        # Pass 3: write each document.
        for src, doc, chunks in ([] if dry_run else changed):
            # Replace the document's chunks atomically: readers see the old or the new version, never half.
            async with conn.transaction():
                doc_id = await conn.fetchval(
                    """
                    INSERT INTO ai.documents (source_path, title, category, content_hash)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (source_path) DO UPDATE
                        SET title = EXCLUDED.title, category = EXCLUDED.category,
                            content_hash = EXCLUDED.content_hash, updated_at = now()
                    RETURNING id
                    """,
                    src.source_path, doc.title, src.category, src.file_hash,
                )
                await conn.execute("DELETE FROM ai.chunks WHERE document_id = $1", doc_id)
                await conn.executemany(
                    """
                    INSERT INTO ai.chunks (document_id, chunk_index, heading, content, token_estimate,
                                           content_hash, embedding, embedding_model)
                    VALUES ($1, $2, $3, $4, $5, $6, $7::vector, $8)
                    """,
                    [
                        (doc_id, c.index, c.heading, c.content, c.token_estimate, c.content_hash,
                         new_vectors.get(c.content_hash) or reusable[c.content_hash], embedder.model)
                        for c in chunks
                    ],
                )
            report.chunks_written += len(chunks)

        # Documents whose files were deleted. Chunks go with them (ON DELETE CASCADE).
        current = {s.source_path for s in sources}
        stale = [p for p in existing if p not in current]
        report.removed.extend(stale)
        if stale and not dry_run:
            await conn.execute("DELETE FROM ai.documents WHERE source_path = ANY($1::text[])", stale)

    return report


async def _reusable_embeddings(conn: asyncpg.Connection, chunks: list[Chunk], model: str) -> dict[str, str]:
    if not chunks:
        return {}
    rows = await conn.fetch(
        """
        SELECT DISTINCT ON (content_hash) content_hash, embedding::text AS embedding
        FROM ai.chunks
        WHERE content_hash = ANY($1::text[]) AND embedding_model = $2
        """,
        [c.content_hash for c in chunks], model,
    )
    return {r["content_hash"]: r["embedding"] for r in rows}


def make_embedder(settings: Settings) -> GeminiEmbedder:
    if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value():
        raise SystemExit("GEMINI_API_KEY is empty. Paste your key into ai_service/.env first.")
    return GeminiEmbedder(
        settings.gemini_api_key.get_secret_value(),
        settings.gemini_embedding_model,
        settings.embedding_dimensions,
        texts_per_minute=settings.gemini_embed_texts_per_minute,
    )


async def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    settings = get_settings()
    if settings.database_url is None:
        raise SystemExit("AI_DATABASE_URL is not set")

    class _DryRunEmbedder:
        model = settings.gemini_embedding_model
        dimensions = settings.embedding_dimensions

    embedder = _DryRunEmbedder() if args.dry_run else make_embedder(settings)
    pool = await asyncpg.create_pool(settings.database_url.get_secret_value(), min_size=1, max_size=2)
    try:
        report = await ingest(
            pool, embedder, settings.knowledge_dir,
            max_tokens=settings.chunk_max_tokens, overlap_tokens=settings.chunk_overlap_tokens,
            dry_run=args.dry_run,
        )
    finally:
        await pool.close()
        if hasattr(embedder, "aclose"):
            await embedder.aclose()

    summary = asdict(report)
    if not args.dry_run:
        summary["api_usage"] = asdict(embedder.usage)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
