"""Split Markdown knowledge documents into retrieval-sized chunks.

Design:
- Split on headings first, so a chunk never mixes two topics. Each chunk keeps its
  heading path ("Credit cards in PPA > Recording a payment") as context.
- Inside a long section, pack whole paragraphs up to a token budget. A table or list
  stays in one piece where possible.
- A small overlap (the previous paragraph) carries context across a split.

Token counts are estimated as characters / 4. That is close enough for budgeting and
avoids depending on a tokenizer that differs between Groq and Gemini anyway.
"""

import hashlib
import math
import re
from dataclasses import dataclass, field

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Chunk:
    index: int
    heading: str
    content: str

    @property
    def embedding_text(self) -> str:
        """What gets embedded: heading path + content, so a chunk is understandable on its own."""
        return f"{self.heading}\n\n{self.content}"

    @property
    def token_estimate(self) -> int:
        return estimate_tokens(self.embedding_text)

    @property
    def content_hash(self) -> str:
        return sha256(self.embedding_text)


@dataclass
class ParsedDocument:
    title: str
    metadata: dict[str, str]
    body: str
    sections: list[tuple[str, str]] = field(default_factory=list)  # (heading path, text)


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Simple `key: value` front matter between --- lines (no YAML dependency needed)."""
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    metadata = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip()
    return metadata, text[end + 5:]


def parse_document(text: str) -> ParsedDocument:
    metadata, body = parse_front_matter(text)
    stack: list[tuple[int, str]] = []  # (level, heading)
    sections: list[tuple[str, str]] = []
    buffer: list[str] = []
    in_fence = False
    title = metadata.get("title")

    def flush():
        content = "\n".join(buffer).strip()
        if content:
            path = " > ".join(h for _, h in stack) or (title or "Untitled")
            sections.append((path, content))
        buffer.clear()

    for line in body.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
        match = None if in_fence else HEADING_RE.match(line)
        if match:
            flush()
            level, heading = len(match.group(1)), match.group(2).strip()
            if level == 1 and title is None:
                title = heading
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, heading))
        else:
            buffer.append(line)
    flush()
    return ParsedDocument(title=title or "Untitled", metadata=metadata, body=body, sections=sections)


def _split_blocks(text: str) -> list[str]:
    """Paragraphs separated by blank lines. Tables and lists stay together as one block."""
    return [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]


def _split_oversized(block: str, max_tokens: int) -> list[str]:
    """Split a single block that is too long: by lines (tables, lists), then sentences, then characters."""
    if estimate_tokens(block) <= max_tokens:
        return [block]
    units = block.splitlines() if "\n" in block else SENTENCE_RE.split(block)
    if len(units) == 1:
        size = max_tokens * 4
        return [block[i:i + size] for i in range(0, len(block), size)]
    parts, current = [], ""
    for unit in units:
        candidate = f"{current}\n{unit}" if current else unit
        if current and estimate_tokens(candidate) > max_tokens:
            parts.append(current)
            current = unit
        else:
            current = candidate
    if current:
        parts.append(current)
    # A single unit may still be too long; split it further.
    return [p for part in parts for p in (_split_oversized(part, max_tokens) if part != block else [part])]


def chunk_document(text: str, *, max_tokens: int = 350, overlap_tokens: int = 60) -> tuple[ParsedDocument, list[Chunk]]:
    doc = parse_document(text)
    chunks: list[Chunk] = []

    for heading, section_text in doc.sections:
        # Budget for the content, leaving room for the heading line that is embedded too.
        budget = max(50, max_tokens - estimate_tokens(heading) - 2)
        blocks = [p for b in _split_blocks(section_text) for p in _split_oversized(b, budget)]
        current: list[str] = []
        for block in blocks:
            candidate = "\n\n".join(current + [block])
            if current and estimate_tokens(candidate) > budget:
                chunks.append(Chunk(len(chunks), heading, "\n\n".join(current)))
                # Overlap: carry the last paragraph forward if it is short.
                last = current[-1]
                carry = [last] if estimate_tokens(last) <= overlap_tokens else []
                if carry and estimate_tokens("\n\n".join(carry + [block])) > budget:
                    carry = []
                current = carry + [block]
            else:
                current.append(block)
        if current:
            chunks.append(Chunk(len(chunks), heading, "\n\n".join(current)))
    return doc, chunks
