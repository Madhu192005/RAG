# WasteWise AI RAG Knowledge Base (Steps 5–6)

Step 5 provides document ingestion and vector retrieval. Step 6 connects the assistant endpoint to hybrid retrieval, reranking, grounded Groq generation, citation validation, and authenticated conversation history.

## Architecture

`PDF -> page-level PyMuPDF extraction -> conservative text cleaning -> paragraph-aware chunks -> normalized Sentence Transformers embeddings -> FAISS inner-product search`

The source PDF is never removed. Original page text is stored in `vector_store/metadata/raw_text/`; chunk text and chunk metadata are mapped by FAISS vector ID in `vector_store/faiss_index/index_metadata.json`. `document_registry.json` records checksums, source metadata, processing outcomes, and historical versions. MySQL tracks documents, versions, ingestion jobs, and chunk-to-vector references; embeddings remain outside MySQL.

## Collecting official source documents

Prefer primary sources: CPCB, MoEFCC, Government of India notifications, TNPCB, or verified Tiruchirappalli municipal publications. Confirm the issuing authority, publication/effective dates, applicable jurisdiction, and whether a superseding document exists before marking a source `current`. The pipeline does not download sources or infer that a document is current. Do not populate those facts from an unverified webpage or filename.

Official starting points (not assertions that every linked page or document is current):

- [CPCB solid-waste management portal](https://swm.cpcb.gov.in/)
- [CPCB guidelines](https://cpcb.gov.in/web/guidelines/)
- [CPCB e-waste portal](https://www.eprewaste.cpcb.gov.in/)
- [CPCB plastic-waste portal](https://pwm.cpcb.gov.in/)
- [Press Information Bureau](https://www.pib.gov.in/)

No source PDFs are included in this repository. Add only PDFs that you have independently verified under the appropriate `knowledge_base/` subdirectory. This avoids representing a guessed or unverified regulation as authoritative.

## Setup

From the repository root, activate the Python environment used for the backend and install:

```powershell
python -m pip install -r backend/requirements.txt
```

Set up MySQL as described in [DATABASE_SETUP.md](./DATABASE_SETUP.md), then apply both migrations:

```powershell
Set-Location backend
python -m alembic upgrade head
Set-Location ..
```

The ingestion CLI writes document metadata and job records to the configured MySQL database by default. To run locally without MySQL, pass `--local-only`; that mode stores the registry and index on disk only.

## Add PDFs

Run interactively:

```powershell
python -m ai_engine.ingestion.ingestion_pipeline
```

Or supply a file/folder and verified metadata:

```powershell
python -m ai_engine.ingestion.ingestion_pipeline `
  --path knowledge_base/national `
  --authority "CPCB" `
  --jurisdiction "national" `
  --category "municipal_solid_waste" `
  --source-url "https://official-source.example/document.pdf" `
  --status unknown
```

The URL above is a format example, not a document citation. Replace it only with the verified URL of the exact source file. Do not set dates or `current` status unless verified. For a test or local-only ingest, append `--local-only`.

The command accepts one PDF or recursively scans a directory for PDFs. Each file is handled independently. The report includes success/failure/duplicate counts, pages, chunks, duration, OCR-required pages, and errors. A failed file does not prevent other files from processing.

Change a verified document's registry/database status without re-ingesting its PDF:

```powershell
python -m ai_engine.ingestion.ingestion_pipeline --document-id <document-uuid> --mark-status superseded
```

Use `--local-only` only when intentionally operating without MySQL.

Rebuild the index from retained extracted page text into a staging directory. The old index is retained as a timestamped backup until an operator removes it:

```powershell
python -m ai_engine.ingestion.ingestion_pipeline --rebuild-index
```

## Extraction, cleaning, and chunking

PyMuPDF extracts each page separately and records 1-based page numbers. Empty pages are explicitly flagged as requiring OCR; OCR is not implemented. Extracted original text is retained. Cleaning normalizes Unicode and whitespace without stripping legal clauses, section numbering, tables, warnings, or repeated page text based on guesses. Chunking targets about 500 simple tokenizer units with 100 units of overlap and carries source, jurisdiction, category, version, page-range, and heading metadata. These limits can be changed through `ingest_paths`.

## Embeddings and FAISS

The default model is `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, selected for English/Tamil support. Model loading is lazy; embeddings are normalized and generated in batches on CPU unless a different device is configured programmatically. Dimensions come from the loaded model and are not hardcoded. The model name and package version are recorded.

FAISS uses `IndexIDMap2(IndexFlatIP)` over normalized vectors, making inner-product ranking equivalent to cosine ranking. The index and vector-ID-to-chunk metadata are stored separately. Loading checks model identity and index/metadata ID consistency. Do not load FAISS files from untrusted sources. Index rebuilds must use the retained source PDFs; do not delete the source folder.

## Registry and MySQL metadata

SHA-256 checksums prevent re-ingestion of successfully processed identical PDFs. Changed files are retained as additional versions under a stable document identity; the pipeline never promotes a version to current automatically. Status values are `unknown`, `current`, `superseded`, or `inactive`. Failed attempts may be retried. The Alembic migration adds `knowledge_documents`, `document_versions`, `document_chunks`, and `ingestion_jobs`; foreign keys use restrictive deletion so historical records are not accidentally removed.

Review the registry and the database together before manually changing a source status. The FAISS index can be recreated from retained PDFs and metadata; use a separate backup before replacing production index files.

## Grounded assistant (Step 6)

Configure `GROQ_API_KEY` and `GROQ_MODEL` in the backend `.env`. The model name must be supported for the account. The assistant uses semantic FAISS search and BM25, reciprocal-rank fusion, and a lazily loaded Cross-Encoder. If reranking is unavailable, fused retrieval is used with a warning. Groq is not called when the index contains no eligible evidence.

The assistant endpoint remains `POST /api/assistant/chat` and accepts the legacy `message` field or the preferred `question` field, plus optional location and metadata filters. Responses include confidence labels, source excerpts, page/version provenance, citation IDs, retrieval metadata, and warnings. Every answer sentence must cite a retrieved `[C#]` source; unknown or invalid citations are discarded and yield the exact insufficient-evidence response. Superseded and inactive documents are excluded. Documents whose current status is unknown may be cited with a warning, and location requests without a matching local source are explicitly cautioned.

Anonymous chats are not stored. Authenticated requests return a `session_id`; send it on later turns to continue that conversation. The server verifies ownership and uses recent history only to resolve follow-up references, while performing fresh retrieval for every turn. A new Alembic migration creates the conversation tables:

```powershell
Set-Location backend
python -m alembic upgrade head
Set-Location ..
```

The frontend retains the active session ID for the current browser session and starts a fresh conversation when chat is cleared.

`ai_engine.ingestion.retrieval.DocumentRetriever` remains available for direct vector-only retrieval. The assistant route uses `ai_engine.retrieval` hybrid components and the grounded generation modules under `ai_engine/generation`.

## Tests and checks

From the repository root:

```powershell
python -m pytest tests -q
```

Run page-level extraction against an operator-supplied PDF:

```powershell
python -m ai_engine.evaluation.extraction_tests path\to\verified-document.pdf
```

`ai_engine/evaluation/retrieval_dataset.json` contains evaluation questions and expected source authorities/categories, not claims about retrieval accuracy. No score should be reported until actual verified source files have been indexed and evaluated. The repository currently contains no verified source PDFs; therefore, useful retrieval accuracy and Groq-grounded answer quality have not been evaluated.

## Troubleshooting

| Error | Resolution |
| --- | --- |
| No text on a page / `needs_ocr_pages` | The PDF may be scanned. OCR is not included; obtain a text-searchable official copy or add OCR as a separately validated enhancement. |
| Encrypted or malformed PDF | Obtain a valid, readable source copy and verify its provenance. |
| Model download/loading failure | Check model repository access and available disk space; retry with the configured CPU device. |
| FAISS model mismatch | Use the same embedding model as the existing index or rebuild into a separate index directory. |
| FAISS metadata mismatch | Restore a matching index/metadata backup or rebuild from source PDFs. Do not hand-edit vector IDs. |
| MySQL connection error | Start/configure MySQL and verify `.env`, then run `alembic upgrade head`. |
| Duplicate skipped | The exact file checksum has already been processed; modified content creates a distinct version. |
