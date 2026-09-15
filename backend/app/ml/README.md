# OMNITorch — local ML subsystem

OMNITorch v0.2 adds preserved image intake, immutable dataset snapshots, explicit
CPU training, separate evaluation, a local checkpoint registry and inference.
See [the v0.2 architecture and API contract](../../../docs/OMNITORCH_V02.md).

The sections below document the retained **v0.1 demo inference path**. Statements
about its limitations apply to that bundled classifier, not the v0.2 workflow.

## Legacy inference subsystem

OMNITorch is OMNI's PyTorch-powered image inference layer.

It wraps registered ML models behind a stable API so OMNI agents
(Pluto, QaZ, Korva) and the frontend can consume ML output without
caring about the underlying model architecture.

## What it does now

- Runs the Fashion-MNIST MLP demo classifier
- Returns structured `OMNITorchResult` JSON for every inference
- Reports runtime info (device, torch version, CUDA availability, inference time)
- Generates OMNI-readable interpretation (summary, engineering relevance, limitations)
- Serves a model registry listing via `/api/ml/models`
- Caches models in memory — no reload per request

## What it does NOT do yet

- It does not understand CAD geometry, robot components, or PCB layouts
- It does not replace engineering judgment
- It does not support GPU inference in the current deployment (CPU only unless CUDA is present)
- The Fashion-MNIST model has no knowledge of OMNI mission outputs

## Architecture

```
ml_routes.py           — FastAPI routes (/api/ml/*)
omnitorch_service.py   — Main inference service (model cache, preprocessing, result packaging)
omnitorch_schemas.py   — Pydantic result schemas (OMNITorchResult, etc.)
model_registry.py      — Registry of available models and their card files
inference_service.py   — Backward-compat wrapper for legacy callers
reports.py             — OMNI interpretation layer (converts raw predictions to OMNI language)
fashion_mnist_model.py — MLP model architecture
models/
  fashion_mnist_mlp.pt           — Trained weights
  fashion_mnist_mlp.card.json    — Model metadata card
```

## Testing

Start backend:
```bash
cd AI_Avengers_HQ
uvicorn backend.app.main:app --reload --port 8000
```

Start frontend:
```bash
cd frontend
npm run dev
```

Status check:
```bash
curl http://localhost:8000/api/ml/status
```

Model list:
```bash
curl http://localhost:8000/api/ml/models
```

Image classification (replace test_image.png with a real image):
```bash
curl -X POST http://localhost:8000/api/ml/classify-demo \
  -F "file=@test_image.png"
```

Full analyze-image with model selection:
```bash
curl -X POST http://localhost:8000/api/ml/analyze-image \
  -F "file=@test_image.png" \
  -F "model_name=fashion_mnist_mlp"
```

## Evolution path

```
Fashion-MNIST demo classifier
        ↓
OMNITorch standard result format  ← you are here
        ↓
CAD screenshot upload
        ↓
Rule-based visual critique
        ↓
Labeled CAD morphology dataset
        ↓
Trained CAD morphology model
        ↓
OMNI Forge visual validation
```

## Adding a new model

1. Train or obtain a `.pt` weights file
2. Add a `.card.json` to `models/`
3. Register it in `model_registry.py`
4. Add an interpreter function in `reports.py`
5. If the architecture differs from FashionMNISTModel, add a factory case in `omnitorch_service._load_model()`

## Safety note

OMNITorch results are not engineering decisions. Human review is required
before acting on any model output in a physical engineering context.
