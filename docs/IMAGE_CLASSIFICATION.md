# Step 7: Waste image classification

## Current status

The code supports eight target classes, private authenticated uploads, history and confirmation endpoints, a MobileNetV3-Large training pipeline, test evaluation, and a handoff to the existing grounded RAG service. This repository contains no dataset images or trained checkpoint. Consequently there are no evaluation metrics and `/api/classification/predict` returns HTTP 503 until training has produced `models/waste_classifier/mobilenet_v3_large.pt`. No model accuracy is claimed.

## Dataset and licensing

No data was found in `dataset/` in this checkout. `dataset/raw/<safe class folder>/` is the required staging layout. Review and record the license for every image before use.

- [TrashNet](https://github.com/garythung/TrashNet) is a small six-class dataset (glass, paper, cardboard, plastic, metal, trash); the repository supplies an MIT license. It does not provide organic/food, sanitary, or battery/e-waste examples and cannot train all eight classes by itself. It may be used only after checking the source license file and mapping each image appropriately. The combined Paper / Cardboard class can include its two paper classes.
- [TACO](https://github.com/pedropro/TACO) supplies litter object annotations, not these eight image-level labels. Annotation license and source image licenses are separate concerns; inspect each image's recorded license and use only images whose terms permit the intended use. Its labels need an explicit reviewed conversion to the target taxonomy; do not map broad or ambiguous items to hazardous/sanitary classes by appearance alone.

For example, the preparation script accepts the TrashNet source folder names `paper`, `cardboard`, `glass`, `plastic`, `metal`, and `trash`; paper and cardboard merge into one target label and trash maps to the manual-review residual class. For other sources, manually review and curate files into these safe target folder names:

```text
dataset/raw/Plastic/
dataset/raw/Paper_Cardboard/
dataset/raw/Metal/
dataset/raw/Glass/
dataset/raw/Organic_Food/
dataset/raw/Sanitary Products/
dataset/raw/Battery_E-Waste/
dataset/raw/Other_Unknown/
```

Images are ignored by Git. `dataset.py` validates actual JPEG/PNG/WebP content, rejects corrupt or out-of-range dimensions, detects exact-byte duplicates with SHA-256, applies the explicit source-folder mapping, creates seeded 70/15/15 train/validation/test splits, and writes `dataset/processed/class_distribution.json` including the mapping and counts. Near-duplicate detection is not implemented. Keep related photos of the same physical object in one split manually to prevent leakage. Do not train until every class has meaningful, reviewed examples; the script reports counts rather than silently manufacturing missing classes.

Download source archives from the original TrashNet README/Hugging Face dataset page or clone the TACO repository, keep the original archives and license metadata outside the web root, then extract into `dataset/raw` and manually curate/relabel into the exact class-folder names above. TACO's helper downloads images with `python download.py` from the TACO checkout; review the source image terms and annotations before using any image. Neither download is an eight-class ready-to-train dataset. Keep an accompanying source/rights manifest for each curated item; the split script preserves filenames as hashes and does not replace that provenance record.

## Mapping and safety

The default mapping is Plastic, Paper / Cardboard, Metal, Glass → Dry waste; Organic / Food → Wet waste; Sanitary Products → Sanitary waste; Battery / E-Waste → Special-care waste; Other / Unknown → Requires manual review. Override mappings with the `WASTE_CLASS_MAPPING` JSON environment variable. Local collection rules must still come from cited RAG sources. The model cannot identify contents, contamination, chemicals, medicines, or battery chemistry from appearance. Sanitary, battery/e-waste, unknown, and below-threshold results require user review. A metallic appearance is not proof that an item belongs in ordinary recycling.

## Model, preprocessing, training

The model factory uses Torchvision MobileNetV3-Large with an eight-output head. Inputs are RGB, 224×224, ImageNet mean/std normalized. Training augments with horizontal flips, uses AdamW and cross-entropy, balanced sampling for class imbalance, reproducible seeds, a held-out validation split, and patience-based early stopping. It detects CUDA and otherwise runs on CPU (expect CPU training to be slow; no GPU is required). Torchvision's ImageNet weights are fetched by its supported pretrained-weight mechanism during training; inference never downloads weights.

Install backend dependencies from `backend/requirements.txt`, then from the repository root run:

```powershell
python -m ai_engine.classification.dataset --raw dataset/raw --output dataset/processed --seed 42
python -m ai_engine.classification.train --data dataset/processed --epochs 20 --batch-size 32 --seed 42
python -m ai_engine.classification.evaluate --data dataset/processed --checkpoint models/waste_classifier/mobilenet_v3_large.pt
```

Temperature scaling is fitted on validation logits and stored in the checkpoint. Evaluation reports metrics on the separate test split in `models/waste_classifier/evaluation.json`; do not use validation performance as the final score. Review per-class sanitary and special-care recall and confusion-matrix errors before using the model. The score is a temperature-scaled softmax score, not a guarantee of correctness.

## Inference and API

The inference service loads one checkpoint lazily and caches it for the process lifetime. `WASTE_MODEL_DIR`, `WASTE_UNCERTAINTY_THRESHOLD` (default 0.55), `WASTE_MAX_UPLOAD_BYTES` (default 10 MiB), and `WASTE_UPLOAD_DIR` configure the service. Pillow validates decoded image content; file extensions and claimed MIME types are not trusted. OpenCV is installed for optional image tooling; primary decode/validation uses Pillow.

Apply the schema migration from `backend/` using `alembic upgrade head`. Run the FastAPI app as documented in `docs/DATABASE_SETUP.md`. Endpoints require the existing Bearer token:

- `POST /api/classification/predict` multipart fields: `file`, optional `location`, optional `user_confirmation`.
- `GET /api/classification/classes`
- `GET /api/classification/history` and `GET /api/classification/history/{prediction_id}`
- `POST /api/classification/confirm` JSON: `{"prediction_id": 1, "confirmed_class": "Plastic"}`

Files are stored under `.private_uploads/classification` (or `WASTE_UPLOAD_DIR`), outside the frontend static tree. MySQL stores only the relative reference. History lookup and confirmation are restricted to the signed-in owner. The prediction route calls the existing `GroundedRAGService`, which retains hybrid FAISS/BM25 retrieval, RRF, reranking, Groq generation, and citation validation. If the evidence pipeline cannot answer, no disposal instruction is invented; the user sees the insufficient-evidence response or a guidance-unavailable state.

## Tests and limitations

Run `pytest` from the repository root after installing backend requirements. The API tests mock model and RAG boundaries; exercise a real checkpoint and curated held-out images with the training/evaluation commands above. No real-model evaluation was possible for this checkout because neither licensed labeled images nor a checkpoint is present. Dataset coverage, class balance, lighting/domain shift, multiple items per image, obscured labels, and especially sanitary/special-care false negatives remain unmeasured until a reviewed dataset is supplied.
