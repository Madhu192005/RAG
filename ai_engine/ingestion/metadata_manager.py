"""Versioned JSON document registry with checksum-based duplicate detection."""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from ai_engine.utils.file_hash import sha256_file


class DocumentRegistry:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            with path.open("r", encoding="utf-8") as source:
                self.data = json.load(source)
            if not isinstance(self.data, dict) or not isinstance(self.data.get("documents"), list):
                raise ValueError(f"Invalid document registry format: {path}")
        else:
            self.data = {"schema_version": 1, "documents": []}

    def find_checksum(self, checksum: str) -> Optional[Dict[str, Any]]:
        return next(
            (
                version
                for document in self.data["documents"]
                for version in document.get("versions", [])
                if version.get("checksum") == checksum
                and version.get("processing_status") in {"processed", "processed_with_ocr_required"}
            ),
            None,
        )

    def add_version(
        self,
        *,
        source_path: Path,
        metadata: Dict[str, Any],
        checksum: Optional[str] = None,
        page_count: int,
        chunk_count: int,
        status: str = "processed",
        save: bool = True,
        version_id: Optional[str] = None,
        vector_ids: Optional[list] = None,
        chunk_size_tokens: int = 500,
        chunk_overlap_tokens: int = 100,
    ) -> Dict[str, Any]:
        checksum = checksum or sha256_file(source_path)
        if self.find_checksum(checksum):
            raise ValueError("This document checksum is already registered.")
        document_id = metadata.get("document_id") or str(uuid4())
        document = next(
            (item for item in self.data["documents"] if item.get("document_id") == document_id),
            None,
        )
        if document is None:
            document = {
                "document_id": document_id,
                "title": metadata["title"],
                "source_authority": metadata.get("source_authority"),
                "source_url": metadata.get("source_url"),
                "jurisdiction": metadata.get("jurisdiction"),
                "document_category": metadata.get("document_category"),
                "status": metadata.get("status", "unknown"),
                "versions": [],
            }
            self.data["documents"].append(document)
        version = {
            "version_id": version_id or str(uuid4()),
            "original_filename": source_path.name,
            "checksum": checksum,
            "publication_date": metadata.get("publication_date"),
            "effective_date": metadata.get("effective_date"),
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "processing_status": status,
            "page_count": page_count,
            "chunk_count": chunk_count,
            "embedding_model": metadata.get("embedding_model"),
            "embedding_model_version": metadata.get("embedding_model_version"),
            "vector_ids": vector_ids or [],
            "chunk_size_tokens": chunk_size_tokens,
            "chunk_overlap_tokens": chunk_overlap_tokens,
        }
        document["versions"].append(version)
        if save:
            self.save()
        return {"document": document, "version": version}

    def remove_version(self, version_id: str) -> None:
        for document in self.data["documents"]:
            document["versions"] = [
                version for version in document.get("versions", [])
                if version.get("version_id") != version_id
            ]
        self.data["documents"] = [
            document for document in self.data["documents"] if document.get("versions")
        ]
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self.path.parent),
                delete=False,
                suffix=".tmp",
            ) as output:
                json.dump(self.data, output, ensure_ascii=False, indent=2)
                output.write("\n")
                temporary_path = output.name
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.unlink(temporary_path)
