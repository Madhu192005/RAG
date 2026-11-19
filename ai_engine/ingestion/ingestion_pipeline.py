"""Resilient PDF-to-FAISS ingestion pipeline and CLI."""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import NAMESPACE_URL, uuid5

from ai_engine.ingestion.chunker import chunk_document
from ai_engine.ingestion.document_loader import load_pdf_paths
from ai_engine.ingestion.embedding_generator import DEFAULT_MODEL, EmbeddingGenerator
from ai_engine.ingestion.metadata_manager import DocumentRegistry
from ai_engine.ingestion.pdf_extractor import ExtractedDocument, ExtractedPage, extract_pdf
from ai_engine.ingestion.vector_index import FaissVectorIndex
from ai_engine.utils.file_hash import sha256_file
from ai_engine.utils.logger import get_logger

ROOT = Path(__file__).resolve().parents[2]
VECTOR_DIR = ROOT / "vector_store"
REGISTRY_PATH = VECTOR_DIR / "metadata" / "document_registry.json"
INDEX_DIR = VECTOR_DIR / "faiss_index"
RAW_DIR = VECTOR_DIR / "metadata" / "raw_text"


def _validate_metadata(metadata: Dict[str, Any], source_path: Path) -> Dict[str, Any]:
    title = str(metadata.get("title") or source_path.stem).strip()
    if not title:
        raise ValueError(f"A document title is required for {source_path.name}.")
    current_status = metadata.get("status", "unknown")
    if current_status not in {"unknown", "current", "superseded", "inactive"}:
        raise ValueError("status must be unknown, current, superseded, or inactive.")
    normalized = dict(metadata)
    for date_field in ("publication_date", "effective_date"):
        value = normalized.get(date_field)
        if value is not None:
            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value)):
                    raise ValueError
                datetime.strptime(str(value), "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError(f"{date_field} must use verified ISO YYYY-MM-DD format.") from exc
    normalized["title"] = title
    normalized["status"] = current_status
    identity = "|".join(
        str(normalized.get(field) or "").strip().casefold()
        for field in ("source_authority", "title", "jurisdiction")
    )
    normalized["document_id"] = normalized.get("document_id") or str(uuid5(NAMESPACE_URL, identity))
    return normalized


def _save_raw_text(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
        ) as output:
            temporary = Path(output.name)
            json.dump(payload, output, ensure_ascii=False, indent=2)
            output.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def ingest_paths(
    input_path: Path,
    metadata: Dict[str, Any],
    *,
    registry_path: Path = REGISTRY_PATH,
    index_directory: Path = INDEX_DIR,
    raw_directory: Path = RAW_DIR,
    embedding_generator: Optional[EmbeddingGenerator] = None,
    db_session=None,
    target_tokens: int = 500,
    overlap_tokens: int = 100,
) -> Dict[str, object]:
    logger = get_logger()
    files = load_pdf_paths(input_path)
    started = datetime.now(timezone.utc)
    start_clock = time.monotonic()
    registry = DocumentRegistry(registry_path)
    model = embedding_generator or EmbeddingGenerator()
    index = FaissVectorIndex(index_directory, model.model_name)
    index.load()

    report: Dict[str, object] = {
        "started_at": started.replace(tzinfo=None),
        "success_count": 0,
        "failed_count": 0,
        "skipped_duplicate_count": 0,
        "page_count": 0,
        "chunk_count": 0,
        "errors": [],
        "documents": [],
    }

    for source_path in files:
        checksum = None
        registered_version_id = None
        try:
            checksum = sha256_file(source_path)
            if registry.find_checksum(checksum):
                report["skipped_duplicate_count"] += 1
                logger.info("Skipped duplicate: %s", source_path.name)
                continue
            doc_metadata = _validate_metadata(metadata, source_path)
            extracted = extract_pdf(source_path)
            raw_version_id = str(uuid5(NAMESPACE_URL, f"{checksum}:{doc_metadata['document_id']}"))
            doc_metadata["document_version_id"] = raw_version_id
            doc_metadata["waste_category"] = doc_metadata.get("document_category")
            _save_raw_text(
                raw_directory / f"{raw_version_id}.json",
                {
                    "filename": source_path.name,
                    "checksum": checksum,
                    "title": extracted.title,
                    "pages": [
                        {
                            "page_number": page.page_number,
                            "text": page.text,
                            "needs_ocr": page.needs_ocr,
                        }
                        for page in extracted.pages
                    ],
                    "needs_ocr_pages": extracted.needs_ocr_pages,
                },
            )
            # Use explicit operator metadata when supplied; otherwise use the PDF title.
            if not metadata.get("title"):
                doc_metadata["title"] = extracted.title
            doc_metadata["document_title"] = doc_metadata["title"]
            doc_metadata["embedding_model"] = model.model_name
            doc_metadata["embedding_model_version"] = model.version
            doc_metadata["chunk_size_tokens"] = target_tokens
            doc_metadata["chunk_overlap_tokens"] = overlap_tokens
            chunks = chunk_document(
                extracted,
                doc_metadata,
                target_tokens=target_tokens,
                overlap_tokens=overlap_tokens,
            )
            if not chunks:
                status = "processed_with_ocr_required" if extracted.needs_ocr_pages else "failed"
                if status == "failed":
                    raise ValueError("No extractable text was found in the PDF.")
            else:
                vectors = model.encode([chunk.text for chunk in chunks])
                previous_ids = {item["chunk_id"] for item in index._metadata.values()}
                vector_ids = index.add(chunks, vectors)
                try:
                    index.save()
                    result = registry.add_version(
                        source_path=source_path,
                        metadata=doc_metadata,
                        checksum=checksum,
                        page_count=len(extracted.pages),
                        chunk_count=len(chunks),
                        status="processed_with_ocr_required" if extracted.needs_ocr_pages else "processed",
                        save=False,
                        version_id=raw_version_id,
                        vector_ids=vector_ids,
                        chunk_size_tokens=target_tokens,
                        chunk_overlap_tokens=overlap_tokens,
                    )
                    registered_version_id = str(result["version"]["version_id"])
                    registry.save()
                    if db_session is not None:
                        from ai_engine.ingestion.mysql_repository import has_checksum, save_document

                        if has_checksum(db_session, checksum):
                            raise ValueError("Document checksum is already stored in MySQL.")
                        save_document(db_session, result["document"], result["version"], chunks, vector_ids)
                except Exception:
                    new_ids = [
                        int(vector_id)
                        for vector_id, value in index._metadata.items()
                        if value["chunk_id"] not in previous_ids
                    ]
                    index.remove(new_ids)
                    index.save()
                    if registered_version_id:
                        registry.remove_version(registered_version_id)
                    raise
                report["chunk_count"] += len(chunks)
                report["page_count"] += len(extracted.pages)
                report["success_count"] += 1
                document_result = {
                    "filename": source_path.name,
                    "document_id": result["document"]["document_id"],
                    "version_id": result["version"]["version_id"],
                    "checksum": checksum,
                    "page_count": len(extracted.pages),
                    "chunk_count": len(chunks),
                    "needs_ocr_pages": extracted.needs_ocr_pages,
                    "processing_status": result["version"]["processing_status"],
                }
                report["documents"].append(document_result)
                logger.info(
                    "Ingested %s: %d pages, %d chunks%s",
                    source_path.name,
                    len(extracted.pages),
                    len(chunks),
                    f"; OCR needed on pages {extracted.needs_ocr_pages}" if extracted.needs_ocr_pages else "",
                )
                continue

            result = registry.add_version(
                source_path=source_path,
                metadata=doc_metadata,
                checksum=checksum,
                page_count=len(extracted.pages),
                chunk_count=0,
                status="processed_with_ocr_required",
                save=False,
                version_id=raw_version_id,
                chunk_size_tokens=target_tokens,
                chunk_overlap_tokens=overlap_tokens,
            )
            registered_version_id = str(result["version"]["version_id"])
            registry.save()
            if db_session is not None and not chunks:
                from ai_engine.ingestion.mysql_repository import save_document

                save_document(db_session, result["document"], result["version"], [], [])
            report["page_count"] += len(extracted.pages)
            report["success_count"] += 1
            report["documents"].append(
                {
                    "filename": source_path.name,
                    "document_id": result["document"]["document_id"],
                    "version_id": result["version"]["version_id"],
                    "checksum": checksum,
                    "page_count": len(extracted.pages),
                    "chunk_count": 0,
                    "needs_ocr_pages": extracted.needs_ocr_pages,
                    "processing_status": "processed_with_ocr_required",
                }
            )
        except Exception as exc:
            if registered_version_id:
                registry.remove_version(registered_version_id)
            report["failed_count"] += 1
            error = {"filename": source_path.name, "error": str(exc)}
            report["errors"].append(error)
            logger.exception("Failed to ingest %s", source_path.name)
            if checksum is not None:
                try:
                    registry.add_version(
                        source_path=source_path,
                        metadata=_validate_metadata(metadata, source_path),
                        checksum=checksum,
                        page_count=0,
                        chunk_count=0,
                        status="failed",
                    )
                except Exception as registry_error:
                    error["registry_error"] = str(registry_error)
                    logger.exception("Could not register failed attempt for %s", source_path.name)

    report["finished_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
    report["duration_seconds"] = round(time.monotonic() - start_clock, 3)
    report["status"] = (
        "completed_with_errors"
        if report["failed_count"]
        else "completed"
    )
    if db_session is not None:
        from ai_engine.ingestion.mysql_repository import save_job

        save_job(db_session, report)
    return report


def _prompt_metadata(args: argparse.Namespace) -> Dict[str, Any]:
    def ask(value: Optional[str], label: str) -> Optional[str]:
        return value if value is not None else (input(f"{label} (leave blank if unknown): ").strip() or None)

    return {
        "title": ask(args.title, "Document title"),
        "source_authority": ask(args.authority, "Source authority"),
        "source_url": ask(args.source_url, "Verified source URL"),
        "jurisdiction": ask(args.jurisdiction, "Jurisdiction"),
        "document_category": ask(args.category, "Waste category"),
        "publication_date": ask(args.publication_date, "Verified publication date (ISO YYYY-MM-DD)"),
        "effective_date": ask(args.effective_date, "Verified effective date (ISO YYYY-MM-DD)"),
        "status": ask(args.status, "Document status (unknown/current/superseded/inactive)") or "unknown",
    }


def rebuild_vector_index(
    *,
    registry_path: Path = REGISTRY_PATH,
    raw_directory: Path = RAW_DIR,
    index_directory: Path = INDEX_DIR,
    embedding_generator: Optional[EmbeddingGenerator] = None,
) -> Dict[str, object]:
    """Rebuild a staging index from retained extracted text, then retain a backup."""
    registry = DocumentRegistry(registry_path)
    model = embedding_generator or EmbeddingGenerator()
    parent = index_directory.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging_directory = Path(tempfile.mkdtemp(prefix=f"{index_directory.name}.staging-", dir=parent))
    backup_directory = None
    chunk_count = 0
    document_count = 0
    try:
        staged_index = FaissVectorIndex(staging_directory, model.model_name)
        for document in registry.data["documents"]:
            for version in document.get("versions", []):
                if version.get("processing_status") not in {"processed", "processed_with_ocr_required"}:
                    continue
                raw_path = raw_directory / f"{version['version_id']}.json"
                if not raw_path.exists():
                    raise FileNotFoundError(f"Retained page text is missing for version {version['version_id']}.")
                if version.get("embedding_model") != model.model_name:
                    raise ValueError(
                        f"Version {version['version_id']} uses {version.get('embedding_model')!r}; "
                        f"configured model is {model.model_name!r}."
                    )
                with raw_path.open("r", encoding="utf-8") as source:
                    raw = json.load(source)
                if raw.get("checksum") != version.get("checksum"):
                    raise ValueError(f"Retained page text checksum does not match version {version['version_id']}.")
                pages = [
                    ExtractedPage(
                        page_number=int(page["page_number"]),
                        text=str(page["text"]),
                        needs_ocr=bool(page["needs_ocr"]),
                    )
                    for page in raw["pages"]
                ]
                extracted = ExtractedDocument(
                    source_path=Path(str(version["original_filename"])),
                    title=str(document["title"]),
                    pages=pages,
                    needs_ocr_pages=[page.page_number for page in pages if page.needs_ocr],
                )
                metadata = {
                    "document_id": document["document_id"],
                    "document_version_id": version["version_id"],
                    "document_title": document["title"],
                    "title": document["title"],
                    "source_authority": document.get("source_authority"),
                    "source_url": document.get("source_url"),
                    "jurisdiction": document.get("jurisdiction"),
                    "document_category": document.get("document_category"),
                    "waste_category": document.get("document_category"),
                    "publication_date": version.get("publication_date"),
                    "effective_date": version.get("effective_date"),
                    "status": document.get("status", "unknown"),
                    "embedding_model": version.get("embedding_model"),
                    "embedding_model_version": version.get("embedding_model_version"),
                    "chunk_size_tokens": version.get("chunk_size_tokens", 500),
                    "chunk_overlap_tokens": version.get("chunk_overlap_tokens", 100),
                }
                chunks = chunk_document(
                    extracted,
                    metadata,
                    target_tokens=int(version.get("chunk_size_tokens", 500)),
                    overlap_tokens=int(version.get("chunk_overlap_tokens", 100)),
                )
                if len(chunks) != int(version["chunk_count"]):
                    raise ValueError(
                        f"Chunk count changed for version {version['version_id']}; refusing unsafe rebuild."
                    )
                vectors = model.encode([chunk.text for chunk in chunks])
                ids = version.get("vector_ids") or None
                staged_index.add(chunks, vectors, vector_ids=ids)
                chunk_count += len(chunks)
                document_count += 1

        staged_index.save()
        verified_index = FaissVectorIndex(staging_directory, model.model_name)
        verified_index.load()
        if verified_index.count != chunk_count:
            raise ValueError("Staged FAISS index failed its vector-count verification.")

        if index_directory.exists():
            from uuid import uuid4

            backup_directory = index_directory.with_name(
                f"{index_directory.name}.backup-{uuid4().hex}"
            )
            os.replace(index_directory, backup_directory)
        try:
            os.replace(staging_directory, index_directory)
        except Exception:
            if backup_directory and backup_directory.exists() and not index_directory.exists():
                os.replace(backup_directory, index_directory)
            raise
        return {
            "status": "rebuilt",
            "document_count": document_count,
            "chunk_count": chunk_count,
            "backup_directory": str(backup_directory) if backup_directory else None,
        }
    finally:
        if staging_directory.exists():
            shutil.rmtree(staging_directory)


def set_document_status(
    document_id: str,
    status: str,
    *,
    registry_path: Path = REGISTRY_PATH,
    db_session=None,
) -> Dict[str, str]:
    if status not in {"unknown", "current", "superseded", "inactive"}:
        raise ValueError("status must be unknown, current, superseded, or inactive.")
    registry = DocumentRegistry(registry_path)
    document = next(
        (item for item in registry.data["documents"] if item.get("document_id") == document_id),
        None,
    )
    if document is None:
        raise ValueError(f"Document ID is not in the registry: {document_id}")
    previous_status = document.get("status", "unknown")
    document["status"] = status
    registry.save()
    if db_session is not None:
        from app.models.knowledge import KnowledgeDocument

        row = db_session.query(KnowledgeDocument).filter_by(document_id=document_id).first()
        if row is None:
            document["status"] = previous_status
            registry.save()
            raise ValueError(f"Document ID is not in MySQL: {document_id}")
        row.status = status
        try:
            db_session.commit()
        except Exception:
            db_session.rollback()
            document["status"] = previous_status
            registry.save()
            raise
    return {"document_id": document_id, "status": status}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest official PDF documents into the WasteWise knowledge base.")
    parser.add_argument("--path", type=Path, help="A PDF file or directory containing PDFs.")
    parser.add_argument("--rebuild-index", action="store_true", help="Rebuild FAISS from retained extracted text.")
    parser.add_argument("--mark-status", choices=["unknown", "current", "superseded", "inactive"])
    parser.add_argument("--document-id", help="Document UUID for --mark-status.")
    parser.add_argument("--title", help="Document title (for one PDF).")
    parser.add_argument("--authority", help="Verified source authority.")
    parser.add_argument("--source-url", help="Verified official source URL.")
    parser.add_argument("--jurisdiction", help="Jurisdiction, e.g. national or Tamil Nadu.")
    parser.add_argument("--category", help="Waste category.")
    parser.add_argument("--publication-date", help="Verified publication date, YYYY-MM-DD.")
    parser.add_argument("--effective-date", help="Verified effective date, YYYY-MM-DD.")
    parser.add_argument("--status", choices=["unknown", "current", "superseded", "inactive"])
    parser.add_argument(
        "--embedding-model",
        default=DEFAULT_MODEL,
        help="Sentence Transformers model name.",
    )
    parser.add_argument("--embedding-device", default="cpu", help="Embedding device, normally cpu or cuda.")
    parser.add_argument("--local-only", action="store_true", help="Do not write document metadata to MySQL.")
    args = parser.parse_args(argv)
    model = EmbeddingGenerator(args.embedding_model, device=args.embedding_device)
    if args.rebuild_index:
        try:
            report = rebuild_vector_index(embedding_generator=model)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        except Exception as exc:
            get_logger().error("Index rebuild failed: %s", exc)
            return 1
    if args.mark_status:
        if not args.document_id:
            parser.error("--document-id is required with --mark-status.")
        db_session = None
        try:
            if not args.local_only:
                sys.path.insert(0, str(ROOT / "backend"))
                from app.database.connection import SessionLocal

                db_session = SessionLocal()
            report = set_document_status(
                args.document_id,
                args.mark_status,
                db_session=db_session,
            )
            print(json.dumps(report, indent=2))
            return 0
        except Exception as exc:
            get_logger().error("Could not update document status: %s", exc)
            return 1
        finally:
            if db_session is not None:
                db_session.close()
    path = args.path or Path(input("PDF file or knowledge-base folder: ").strip())
    metadata = _prompt_metadata(args)
    db_session = None
    try:
        if not args.local_only:
            backend_directory = ROOT / "backend"
            sys.path.insert(0, str(backend_directory))
            from app.database.connection import SessionLocal

            db_session = SessionLocal()
        report = ingest_paths(path, metadata, db_session=db_session, embedding_generator=model)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 1 if report["failed_count"] else 0
    except Exception as exc:
        get_logger().error("Ingestion could not start: %s", exc)
        return 1
    finally:
        if db_session is not None:
            db_session.close()


if __name__ == "__main__":
    raise SystemExit(main())
