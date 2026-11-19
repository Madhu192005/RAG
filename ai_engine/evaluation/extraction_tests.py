"""Extraction evaluation helper for validating a manually supplied PDF."""

import argparse
from pathlib import Path

from ai_engine.ingestion.pdf_extractor import extract_pdf
from ai_engine.ingestion.text_cleaner import clean_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect page-level PDF extraction.")
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    document = extract_pdf(args.pdf)
    print(f"Title: {document.title}")
    print(f"Pages: {len(document.pages)}")
    print(f"Pages requiring OCR: {document.needs_ocr_pages}")
    for page in document.pages:
        print(f"\n--- Page {page.page_number} ({'OCR needed' if page.needs_ocr else 'text extracted'}) ---")
        print(clean_text(page.text)[:1000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
