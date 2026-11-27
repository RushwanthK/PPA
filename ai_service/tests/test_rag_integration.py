"""Ingestion, retrieval and migrations against the local pgvector test database
(`ppa_ai_test`). Uses the offline FakeEmbedder: no API calls, no tokens spent."""

import asyncpg
import pytest

from app.migrate import Migration, MigrationError, apply_migrations, load_migrations, render_sql
from app.rag.embeddings import FakeEmbedder
from app.rag.evaluate import EvalCase, evaluate, first_hit_position, score
from app.rag.ingest import ingest
from app.rag.retrieval import reciprocal_rank_fusion, retrieve

pytestmark = pytest.mark.integration

CARDS = """---
title: Credit cards in PPA
category: ppa
---

# Credit cards in PPA

## Recording a payment

Add a payment when you pay the card bill. It reduces used and frees available limit.

## Processing billing

Process billing recalculates billed and unbilled amounts.
"""

FUND = """---
title: Emergency fund
category: finance
---

# Emergency fund

## How much

Keep three to six months of essential expenses for emergencies such as job loss.

## Where to keep it

A savings bank account or a fixed deposit, not stocks.
"""

EPF = """---
title: Provident funds
category: finance
---

# Provident funds

## EPF

Every employee has a UAN that stays the same across jobs.
"""


@pytest.fixture
def knowledge(tmp_path):
    (tmp_path / "ppa").mkdir()
    (tmp_path / "finance").mkdir()
    (tmp_path / "ppa" / "cards.md").write_text(CARDS, encoding="utf-8")
    (tmp_path / "finance" / "fund.md").write_text(FUND, encoding="utf-8")
    (tmp_path / "finance" / "epf.md").write_text(EPF, encoding="utf-8")
    return tmp_path


async def count(pool, table):
    async with pool.acquire() as conn:
        return await conn.fetchval(f"SELECT count(*) FROM ai.{table}")


# ---- Ingestion ---------------------------------------------------------------

async def test_first_ingest_embeds_and_stores_everything(pool, knowledge):
    embedder = FakeEmbedder()
    report = await ingest(pool, embedder, knowledge)
    assert sorted(report.added) == ["finance/epf.md", "finance/fund.md", "ppa/cards.md"]
    assert report.chunks_embedded == report.chunks_written == await count(pool, "chunks")
    assert report.chunks_reused == 0
    assert await count(pool, "documents") == 3


async def test_second_ingest_skips_unchanged_files_without_api_calls(pool, knowledge):
    await ingest(pool, FakeEmbedder(), knowledge)
    embedder = FakeEmbedder()
    report = await ingest(pool, embedder, knowledge)
    assert len(report.unchanged) == 3
    assert report.chunks_embedded == 0
    assert embedder.calls == 0


async def test_editing_one_section_only_re_embeds_that_chunk(pool, knowledge):
    await ingest(pool, FakeEmbedder(), knowledge)
    path = knowledge / "finance" / "fund.md"
    path.write_text(FUND.replace("not stocks.", "never in stocks or crypto."), encoding="utf-8")
    embedder = FakeEmbedder()
    report = await ingest(pool, embedder, knowledge)
    assert report.updated == ["finance/fund.md"]
    assert report.chunks_embedded == 1
    assert report.chunks_reused >= 1
    assert embedder.usage.texts == 1


async def test_deleted_file_removes_document_and_chunks(pool, knowledge):
    await ingest(pool, FakeEmbedder(), knowledge)
    before = await count(pool, "chunks")
    (knowledge / "finance" / "epf.md").unlink()
    report = await ingest(pool, FakeEmbedder(), knowledge)
    assert report.removed == ["finance/epf.md"]
    assert await count(pool, "documents") == 2
    assert await count(pool, "chunks") < before


async def test_changing_embedding_model_re_embeds_everything(pool, knowledge):
    await ingest(pool, FakeEmbedder(), knowledge)
    report = await ingest(pool, FakeEmbedder(model="another-model"), knowledge)
    assert report.unchanged == []
    assert report.chunks_reused == 0
    assert report.chunks_embedded == report.chunks_written


async def test_dry_run_writes_nothing(pool, knowledge):
    embedder = FakeEmbedder()
    report = await ingest(pool, embedder, knowledge, dry_run=True)
    assert len(report.added) == 3 and report.chunks_embedded > 0
    assert report.estimated_tokens_embedded > 0
    assert embedder.calls == 0
    assert await count(pool, "documents") == 0


async def test_folder_outside_known_categories_is_ignored(pool, knowledge):
    (knowledge / "secret").mkdir()
    (knowledge / "secret" / "internal.md").write_text("# Internal\n\nDo not index.", encoding="utf-8")
    report = await ingest(pool, FakeEmbedder(), knowledge)
    assert "secret/internal.md" not in report.added


# ---- Retrieval ---------------------------------------------------------------

async def test_hybrid_retrieval_finds_the_right_document(pool, knowledge):
    embedder = FakeEmbedder()
    await ingest(pool, embedder, knowledge)
    results = await retrieve(pool, embedder, "How do I record a payment for my card bill?", top_k=3)
    assert results[0].source_path == "ppa/cards.md"
    assert results[0].heading == "Credit cards in PPA > Recording a payment"
    assert results[0].vector_similarity is not None


async def test_keyword_search_finds_exact_terms(pool, knowledge):
    embedder = FakeEmbedder()
    await ingest(pool, embedder, knowledge)
    results = await retrieve(pool, embedder, "What is a UAN?", mode="keyword")
    assert results[0].source_path == "finance/epf.md"
    assert results[0].keyword_rank == 1


async def test_category_filter(pool, knowledge):
    embedder = FakeEmbedder()
    await ingest(pool, embedder, knowledge)
    results = await retrieve(pool, embedder, "payment emergency fund", category="finance", top_k=10)
    assert results and all(r.category == "finance" for r in results)


async def test_empty_or_stopword_query(pool, knowledge):
    embedder = FakeEmbedder()
    await ingest(pool, embedder, knowledge)
    assert await retrieve(pool, embedder, "   ") == []
    assert await retrieve(pool, embedder, "what is the", mode="keyword") == []


async def test_evaluation_runs_with_one_embedding_call(pool, knowledge):
    embedder = FakeEmbedder()
    await ingest(pool, embedder, knowledge)
    embedder.calls = 0
    cases = [EvalCase("record a card payment", ("ppa/cards.md",)),
             EvalCase("UAN for EPF", ("finance/epf.md",))]
    results = await evaluate(pool, embedder, cases, top_k=3)
    assert {r.mode for r in results} == {"vector", "keyword", "hybrid"}
    assert embedder.calls == 1  # all questions embedded once, reused for every mode
    hybrid = next(r for r in results if r.mode == "hybrid")
    assert hybrid.hit_at_k == 1.0


# ---- Pure functions ------------------------------------------------------------

def test_reciprocal_rank_fusion_rewards_agreement():
    scores = reciprocal_rank_fusion([1, 2, 3], [3, 1, 4])
    # 1 is ranked high in both lists, 4 only appears once and low.
    assert max(scores, key=scores.get) == 1
    assert scores[4] < scores[3]


def test_metrics():
    assert first_hit_position(["a", "b", "c"], ("b",)) == 2
    assert first_hit_position(["a"], ("z",)) is None
    hit1, hitk, mrr = score([1, 2, None, 1])
    assert (hit1, hitk) == (0.5, 0.75)
    assert mrr == pytest.approx((1 + 0.5 + 0 + 1) / 4)


# ---- Migrations ------------------------------------------------------------------

async def test_migrations_are_idempotent(pool):
    async with pool.acquire() as conn:
        assert await apply_migrations(conn) == []  # already applied by the fixture


async def test_edited_migration_is_detected(pool):
    tampered = [Migration(m.version, m.sql + "\n-- edited") for m in load_migrations()]
    async with pool.acquire() as conn:
        with pytest.raises(MigrationError, match="changed after it was applied"):
            await apply_migrations(conn, tampered)


def test_render_sql_includes_tracking_rows():
    sql = render_sql(load_migrations())
    assert sql.startswith("-- Generated") and "BEGIN;" in sql and sql.rstrip().endswith("COMMIT;")
    assert "INSERT INTO ai.schema_migrations" in sql
    assert "CREATE TABLE ai.chunks" in sql


async def test_ingest_embeds_all_documents_in_one_batched_call(pool, knowledge):
    embedder = FakeEmbedder()
    await ingest(pool, embedder, knowledge)
    assert embedder.calls == 1  # three documents, one embedding call


def test_weighted_fusion_reduces_keyword_influence():
    equal = reciprocal_rank_fusion([1, 2], [2, 1])
    assert equal[1] == equal[2]
    weighted = reciprocal_rank_fusion([1, 2], [2, 1], weights=(1.0, 0.5))
    assert weighted[1] > weighted[2]  # the vector ranking wins ties when keyword weight is lower


class _RecordingConnection:
    """Stands in for a restricted login: the vector extension and the ai schema exist."""

    def __init__(self, schema_exists):
        self.schema_exists = schema_exists
        self.executed = []

    async def fetchval(self, sql, *args):
        return 1 if ("pg_extension" in sql or self.schema_exists) else None

    async def execute(self, sql, *args):
        self.executed.append(" ".join(sql.split()))


async def test_existing_ai_schema_is_not_created_again():
    # Supabase (step 6, Nov 27): the restricted login owns "ai" but may not create schemas, and
    # PostgreSQL checks that permission even for CREATE SCHEMA IF NOT EXISTS.
    from app.migrate import _check_prerequisites
    conn = _RecordingConnection(schema_exists=True)
    await _check_prerequisites(conn)
    assert not any(s.startswith("CREATE SCHEMA") for s in conn.executed)
    fresh = _RecordingConnection(schema_exists=False)
    await _check_prerequisites(fresh)
    assert "CREATE SCHEMA ai" in fresh.executed
