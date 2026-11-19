"""Page-by-page PDF text extraction using PyMuPDF."""

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str
    needs_ocr: bool


@dataclass(frozen=True)
class ExtractedDocument:
    source_path: Path
    title: str
    pages: List[ExtractedPage]
    needs_ocr_pages: List[int]


class PDFExtractionError(RuntimeError):
    """Raised when a PDF cannot be opened or read."""


def extract_pdf(path: Path) -> ExtractedDocument:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PDF extraction requires PyMuPDF; install backend/requirements.txt.") from exc

    try:
        # Open malformed inputs from memory so PyMuPDF cannot retain a Windows
        # file handle after its parser raises. Valid documents follow the same
        # extraction path, while callers can safely replace a failed source.
        with fitz.open(stream=path.read_bytes(), filetype="pdf") as document:
            if document.is_closed or document.is_encrypted:
                raise PDFExtractionError("PDF is encrypted or could not be opened.")
            pages = []
            needs_ocr = []
            for page_index in range(document.page_count):
                page_number = page_index + 1
                page_text = document.load_page(page_index).get_text("text") or ""
                empty = not page_text.strip()
                pages.append(ExtractedPage(page_number, page_text, empty))
                if empty:
                    needs_ocr.append(page_number)
            metadata_title = (document.metadata or {}).get("title")
            title = metadata_title.strip() if metadata_title and metadata_title.strip() else path.stem
        return ExtractedDocument(path, title, pages, needs_ocr)
    except PDFExtractionError:
        raise
    except Exception as exc:
        raise PDFExtractionError(f"Unable to extract PDF '{path.name}': {exc}") from exc
