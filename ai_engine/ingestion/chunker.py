"""Paragraph-aware, page-preserving text chunking with configurable overlap."""

import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Callable, Dict, List, Optional, Sequence
from uuid import NAMESPACE_URL, uuid5

from ai_engine.ingestion.pdf_extractor import ExtractedDocument
from ai_engine.ingestion.text_cleaner import clean_text

_NUMBERED_HEADING = re.compile(
    r"^(?:section\s+\d+|article\s+\d+|\d+(?:\.\d+)*\.?\s+\S.{0,100})$",
    re.IGNORECASE,
)
_TOKEN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def _is_heading(line: str) -> bool:
    return bool(
        _NUMBERED_HEADING.match(line)
        or (
            len(line) >= 4
            and line == line.upper()
            and any(character.isalpha() for character in line)
            and re.fullmatch(r"[A-Z0-9 ,/&()'-]+", line)
        )
    )


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    text: str
    metadata: Dict[str, object]
    token_count: int


def _default_tokens(text: str) -> List[str]:
    return _TOKEN.findall(text)


def _overlap_text(text: str, overlap_tokens: int, tokens: Sequence[object]) -> str:
    if not overlap_tokens or not tokens:
        return ""
    if _default_tokens(text) == list(tokens):
        matches = list(_TOKEN.finditer(text))
        return text[matches[-min(overlap_tokens, len(matches))].start():].strip()
    return " ".join(str(token) for token in tokens[-overlap_tokens:])


def chunk_document(
    document: ExtractedDocument,
    document_metadata: Dict[str, object],
    *,
    target_tokens: int = 500,
    overlap_tokens: int = 100,
    token_counter: Optional[Callable[[str], Sequence[object]]] = None,
) -> List[DocumentChunk]:
    if target_tokens < 1 or overlap_tokens < 0 or overlap_tokens >= target_tokens:
        raise ValueError("Require target_tokens > overlap_tokens >= 0.")

    tokenize = token_counter or _default_tokens
    chunks: List[DocumentChunk] = []
    current_text: List[str] = []
    current_pages: List[int] = []
    section_heading: Optional[str] = None
    current_section_heading: Optional[str] = None

    def emit() -> None:
        nonlocal current_text, current_pages, current_section_heading
        text = clean_text("\n\n".join(current_text))
        if not text:
            return
        page_numbers = sorted(set(current_pages))
        metadata = dict(document_metadata)
        metadata.update(
            {
                "source_filename": document.source_path.name,
                "page_start": page_numbers[0],
                "page_end": page_numbers[-1],
                "page_numbers": page_numbers,
                "section_heading": current_section_heading,
            }
        )
        chunks.append(
            DocumentChunk(
                chunk_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        f"{metadata.get('document_version_id', metadata.get('document_id', 'unknown'))}:"
                        f"{len(chunks)}:{sha256(text.encode('utf-8')).hexdigest()}",
                    )
                ),
                text=text,
                metadata=metadata,
                token_count=len(tokenize(text)),
            )
        )
        overlap = _overlap_text(text, overlap_tokens, list(tokenize(text)))
        current_text = [overlap] if overlap else []
        current_pages = [page_numbers[-1]] if overlap and page_numbers else []
        current_section_heading = section_heading

    for page in document.pages:
        cleaned_page = clean_text(page.text)
        paragraphs = []
        for block in re.split(r"\n\s*\n", cleaned_page):
            lines = block.splitlines()
            current_lines = []
            for line in lines:
                line = line.strip()
                if _is_heading(line) and len(line) < 120:
                    if current_lines:
                        paragraphs.append("\n".join(current_lines))
                        current_lines = []
                    paragraphs.append(line)
                elif line:
                    current_lines.append(line)
            if current_lines:
                paragraphs.append("\n".join(current_lines))

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if _is_heading(paragraph) and len(paragraph) < 120:
                if current_text:
                    emit()
                section_heading = paragraph
                current_section_heading = paragraph
            sentence_units = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", paragraph)
            units = sentence_units if len(sentence_units) > 1 else [paragraph]
            for unit in units:
                words = list(tokenize(unit))
                if not words:
                    continue
                if len(tokenize("\n\n".join(current_text + [unit]))) <= target_tokens:
                    current_text.append(unit)
                    current_pages.append(page.page_number)
                    continue
                if current_text:
                    emit()
                while words:
                    candidate = []
                    while words and len(
                        tokenize(
                            "\n\n".join(
                                current_text + [" ".join(str(part) for part in candidate + [words[0]])]
                            )
                        )
                    ) <= target_tokens:
                        candidate.append(words.pop(0))
                    if not candidate:
                        candidate = [words.pop(0)]
                    text = " ".join(str(token) for token in candidate)
                    current_text.append(text)
                    current_pages.append(page.page_number)
                    if words:
                        emit()
    emit()
    return chunks
