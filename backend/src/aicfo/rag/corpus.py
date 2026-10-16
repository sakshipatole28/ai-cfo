"""Knowledge-base documents and heading-aware chunking.

Documents are Markdown files with a small `key: value` front-matter block.
Each `## Section` becomes one or more chunks of whole sentences, so a
citation always points at a readable passage with its section title.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aicfo.rag.text import sentences

REQUIRED_FIELDS = ("id", "issuer", "title", "source_url", "version", "effective", "kind")


class CorpusError(ValueError):
    """A knowledge-base file is malformed."""


@dataclass(frozen=True)
class Document:
    id: str
    issuer: str
    title: str
    source_url: str
    version: str
    effective: str
    kind: str
    body: str


@dataclass(frozen=True)
class Chunk:
    id: str
    doc: Document
    section: str
    text: str
    ord: int

    @property
    def index_text(self) -> str:
        """What retrieval sees: document title and section help short passages match."""
        return f"{self.doc.title}. {self.section}. {self.text}"


def parse_document(raw: str, source: str = "<memory>") -> Document:
    lines = raw.strip().splitlines()
    if not lines or lines[0].strip() != "---":
        raise CorpusError(f"{source}: missing front matter")
    try:
        end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration as exc:
        raise CorpusError(f"{source}: unterminated front matter") from exc
    meta: dict[str, str] = {}
    for line in lines[1:end]:
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip()
    missing = [f for f in REQUIRED_FIELDS if not meta.get(f)]
    if missing:
        raise CorpusError(f"{source}: missing fields {missing}")
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


def chunk_document(doc: Document, max_chars: int = 700) -> list[Chunk]:
    chunks: list[Chunk] = []
    section = doc.title
    buffer: list[str] = []

    def flush_section(text_lines: list[str], heading: str) -> None:
        text = " ".join(line.strip() for line in text_lines if line.strip())
        if not text:
            return
        current: list[str] = []
        for sentence in sentences(text):
            if current and len(" ".join([*current, sentence])) > max_chars:
                chunks.append(
                    Chunk(f"{doc.id}#{len(chunks)}", doc, heading, " ".join(current), len(chunks))
                )
                current = [current[-1]]  # one sentence of overlap keeps context across the cut
            current.append(sentence)
        if current:
            chunks.append(
                Chunk(f"{doc.id}#{len(chunks)}", doc, heading, " ".join(current), len(chunks))
            )

    for line in doc.body.splitlines():
        if line.startswith("## "):
            flush_section(buffer, section)
            section, buffer = line[3:].strip(), []
        else:
            buffer.append(line)
    flush_section(buffer, section)
    return chunks


def load_corpus(directory: Path) -> tuple[list[Document], list[Chunk]]:
    files = sorted(directory.glob("*.md"))
    if not files:
        raise CorpusError(f"no knowledge-base documents in {directory}")
    docs = [parse_document(f.read_text(encoding="utf-8"), str(f)) for f in files]
    ids = [d.id for d in docs]
    if len(ids) != len(set(ids)):
        raise CorpusError("duplicate document ids")
    return docs, [c for d in docs for c in chunk_document(d)]
