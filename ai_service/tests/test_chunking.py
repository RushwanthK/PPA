from pathlib import Path

import pytest

from app.config import SERVICE_DIR
from app.rag.chunking import chunk_document, estimate_tokens, parse_document, parse_front_matter

KNOWLEDGE = SERVICE_DIR / "knowledge"

DOC = """---
title: Sample guide
category: ppa
---

# Sample guide

Intro paragraph.

## Adding things

Step one.

### Details

Fine print.

## Removing things

Gone.
"""


def test_front_matter_is_parsed_and_removed():
    meta, body = parse_front_matter(DOC)
    assert meta == {"title": "Sample guide", "category": "ppa"}
    assert not body.lstrip().startswith("---")


def test_front_matter_handles_windows_line_endings():
    meta, _ = parse_front_matter(DOC.replace("\n", "\r\n"))
    assert meta["title"] == "Sample guide"


def test_sections_keep_their_heading_path():
    doc = parse_document(DOC)
    assert doc.title == "Sample guide"
    assert [h for h, _ in doc.sections] == [
        "Sample guide",
        "Sample guide > Adding things",
        "Sample guide > Adding things > Details",
        "Sample guide > Removing things",  # the ### level was popped
    ]


def test_title_falls_back_to_first_h1():
    doc = parse_document("# Only a heading\n\nText.")
    assert doc.title == "Only a heading"


def test_hash_signs_inside_code_fences_are_not_headings():
    doc = parse_document("# T\n\n```\n# not a heading\n```\n\n## Real\n\nx")
    assert [h for h, _ in doc.sections] == ["T", "T > Real"]


def test_long_section_is_split_within_budget_with_overlap():
    paragraphs = [f"Paragraph {i}. " + "word " * 60 for i in range(10)]
    text = "# Long\n\n" + "\n\n".join(paragraphs)
    _, chunks = chunk_document(text, max_tokens=200, overlap_tokens=100)
    assert len(chunks) > 1
    assert all(c.token_estimate <= 200 for c in chunks)
    # The last paragraph of one chunk starts the next one (overlap).
    first_last_paragraph = chunks[0].content.split("\n\n")[-1]
    assert chunks[1].content.startswith(first_last_paragraph)
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_single_huge_paragraph_is_split_by_sentences():
    text = "# Big\n\n" + " ".join(f"Sentence number {i} has some words." for i in range(200))
    _, chunks = chunk_document(text, max_tokens=100, overlap_tokens=0)
    assert len(chunks) > 5
    assert all(c.token_estimate <= 100 for c in chunks)


def test_chunk_hash_is_stable_and_changes_with_text():
    _, a = chunk_document(DOC)
    _, b = chunk_document(DOC)
    _, c = chunk_document(DOC.replace("Gone.", "Gone for good."))
    assert [x.content_hash for x in a] == [x.content_hash for x in b]
    changed = [x for x, y in zip(a, c) if x.content_hash != y.content_hash]
    assert len(changed) == 1  # only the edited section


def test_embedding_text_includes_heading_for_context():
    _, chunks = chunk_document(DOC)
    assert chunks[1].embedding_text.startswith("Sample guide > Adding things\n\n")


def test_token_estimate():
    assert estimate_tokens("a") == 1
    assert estimate_tokens("x" * 400) == 100


@pytest.mark.parametrize("path", sorted(KNOWLEDGE.rglob("*.md")), ids=lambda p: p.relative_to(KNOWLEDGE).as_posix())
def test_every_knowledge_document_is_well_formed(path: Path):
    doc, chunks = chunk_document(path.read_text(encoding="utf-8"))
    assert doc.metadata.get("title"), "front matter needs a title"
    assert doc.metadata.get("category") == path.parent.name
    assert doc.metadata.get("last_reviewed")
    assert chunks, "document produced no chunks"
    assert all(c.token_estimate <= 350 for c in chunks)
    if path.parent.name == "finance":
        assert doc.metadata.get("sources"), "finance notes must cite their sources"
        assert "not personal financial advice" in doc.body or "not a recommendation" in doc.body
