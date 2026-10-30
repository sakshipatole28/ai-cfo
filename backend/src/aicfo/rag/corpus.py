"""Knowledge-base documents and heading-aware chunking.

Documents are Markdown files with a small `key: value` front-matter block.
Each `## Section` becomes one or more chunks of whole sentences, so a
citation always points at a readable passage with its section title.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aicfo.rag.text import sentences

# Every knowledge-base file must declare these front-matter fields.
REQUIRED_FIELDS = ("id", "issuer", "title", "source_url", "version", "effective", "kind")


# Raised when a knowledge-base file is malformed.
class CorpusError(ValueError):
    """A knowledge-base file is malformed."""


# A source document (e.g. a SEBI regulation summary).
@dataclass(frozen=True)
class Document:
    # Short stable id, used in citations.
    id: str
    # Who published it.
    issuer: str
    # Document title.
    title: str
    # Official link to the primary source.
    source_url: str
    # Version or date of the text.
    version: str
    # When the rule applies from.
    effective: str
    # Type: regulation, tax, firm policy…
    kind: str
    # The text, with "## Section" headings.
    body: str


# A passage: a few whole sentences from one section of a document.
@dataclass(frozen=True)
class Chunk:
    # Chunk id, "<doc>#<n>".
    id: str
    # The document it came from.
    doc: Document
    # The section heading.
    section: str
    # The passage text.
    text: str
    # Position in the document.
    ord: int

    @property
    # Text used for search: the title and section help short passages match.
    def index_text(self) -> str:
        """What retrieval sees: document title and section help short passages match."""
        # Title. Section. Text.
        return f"{self.doc.title}. {self.section}. {self.text}"


# Read one Markdown file: a front-matter block between --- lines, then the body.
def parse_document(raw: str, source: str = "<memory>") -> Document:
    # Split into lines.
    lines = raw.strip().splitlines()
    # The file must start with ---.
    if not lines or lines[0].strip() != "---":
        # Refuse files without front matter.
        raise CorpusError(f"{source}: missing front matter")
    # Find the closing ---.
    try:
        # Index of the closing --- line.
        end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "---")
    # No closing line.
    except StopIteration as exc:
        raise CorpusError(f"{source}: unterminated front matter") from exc
    # Front-matter values.
    meta: dict[str, str] = {}
    # Each "key: value" line.
    for line in lines[1:end]:
        # Split at the first colon.
        key, sep, value = line.partition(":")
        # Ignore lines without a colon.
        if sep:
            # Store the value.
            meta[key.strip()] = value.strip()
    # Required fields that are absent or empty.
    missing = [f for f in REQUIRED_FIELDS if not meta.get(f)]
    # Incomplete front matter is an error.
    if missing:
        raise CorpusError(f"{source}: missing fields {missing}")
    # Build the document; the rest of the file is its body.
    return Document(
        id=meta["id"],
        issuer=meta["issuer"],
        title=meta["title"],
        source_url=meta["source_url"],
        version=meta["version"],
        effective=meta["effective"],
        kind=meta["kind"],
        body="\n".join(lines[end + 1 :]).strip(),
    )


# Split a document into passages of whole sentences, never crossing a section heading.
def chunk_document(doc: Document, max_chars: int = 700) -> list[Chunk]:
    # Passages so far.
    chunks: list[Chunk] = []
    # Current section heading (the title before the first heading).
    section = doc.title
    # Lines of the current section.
    buffer: list[str] = []

    # Turn the buffered section into one or more passages.
    def flush_section(text_lines: list[str], heading: str) -> None:
        # Join the section's lines into one text.
        text = " ".join(line.strip() for line in text_lines if line.strip())
        # Skip empty sections.
        if not text:
            return
        # Sentences of the passage being built.
        current: list[str] = []
        # Add sentence by sentence.
        for sentence in sentences(text):
            # Too long to add another sentence: close this passage…
            if current and len(" ".join([*current, sentence])) > max_chars:
                # …store it…
                chunks.append(
                    Chunk(f"{doc.id}#{len(chunks)}", doc, heading, " ".join(current), len(chunks))
                )
                # …and start the next with the last sentence repeated, so context carries across the cut.
                current = [current[-1]]  # one sentence of overlap keeps context across the cut
            # Add the sentence.
            current.append(sentence)
        # Store the final passage of the section.
        if current:
            # Store it.
            chunks.append(
                Chunk(f"{doc.id}#{len(chunks)}", doc, heading, " ".join(current), len(chunks))
            )

    # Walk through the body.
    for line in doc.body.splitlines():
        # A new section heading…
        if line.startswith("## "):
            # …finishes the previous section…
            flush_section(buffer, section)
            # …and starts a new one.
            section, buffer = line[3:].strip(), []
        # Ordinary line.
        else:
            # Belongs to the current section.
            buffer.append(line)
    # Finish the last section.
    flush_section(buffer, section)
    # All passages.
    return chunks


# Load every .md file in the knowledge-base folder.
def load_corpus(directory: Path) -> tuple[list[Document], list[Chunk]]:
    # Files in a fixed order, so results are reproducible.
    files = sorted(directory.glob("*.md"))
    # An empty knowledge base is an error.
    if not files:
        raise CorpusError(f"no knowledge-base documents in {directory}")
    # Parse each file.
    docs = [parse_document(f.read_text(encoding="utf-8"), str(f)) for f in files]
    # All document ids.
    ids = [d.id for d in docs]
    # Ids must be unique.
    if len(ids) != len(set(ids)):
        raise CorpusError("duplicate document ids")
    # Documents, and all their passages.
    return docs, [c for d in docs for c in chunk_document(d)]
