# OMNITorch v0.2 — local image learning foundation

## Inspection: behavior before this change

The application is a modular monolith: FastAPI in `backend/app/main.py`, a
React/Vite frontend, and an in-process mission supervisor. Mission execution,
exports and engineering gates do not depend on the ML workspace.

The public overview is `frontend/src/site/PublicHome.jsx`, with factual content
in `siteContent.js`, shared agent identities in `content/agents.js`, and separate
public CSS. `App.jsx` owns console navigation, mission state, result normalization,
execution and export calls. Domain panels consume those results. Visual Bay loads
its Three.js viewer on demand. Console and public views share silver/graphite
tokens and the SVG snail. Prior console navigation used local state beneath
`#/console`; only the landing/console boundary was encoded in the hash.

Existing ML code:

- `model_registry.py`: static allowlist mapping `fashion_mnist_mlp` to a bundled
  weights file and JSON model card. No dynamic registration.
- `fashion_mnist_model.py`: 784 → 128 → 64 → 10 MLP.
- `omnitorch_service.py`: cached model loading, CUDA when available (CPU fallback),
  Pillow decoding, torchvision grayscale/28×28/tensor preprocessing, actual
  logits and softmax, top-three predictions and demonstration interpretation.
- `omnitorch_schemas.py`: prediction/runtime/interpretation/model-card shapes.
- `inference_service.py`: backward-compatible dictionary wrapper.
- `ml_routes.py`: status, models, classify-demo, analyze-image and CAD review.
  Existing classification uploads accept six image MIME types with a 10 MiB
  limit, but read the upload before applying the size check.
- `cad_visual_review.py`: image/edge/foreground heuristics. It is distinct from
  learned classification. Reliability callers interpret these existing shapes.
- `OmniVisionUploadPanel.jsx`: transient upload preview and legacy demo output.
  No persistence, dataset, training, evaluation, or user-trained checkpoint flow.

There was no user-image learning. The model card's benchmark claims are inherited
metadata, not benchmark results reproduced by this task.

## Scope and implementation plan

1. Preserve mission runtime and response contracts. Extract console navigation,
   retain old route IDs, expose engineering sections through existing agent reports,
   improve shared spacing/focus, and remove decorative status indicators and
   simulation of progress. Preserve meaningful validation outcomes.
2. Add isolated ML storage and schemas, using existing Pillow/PyTorch/NumPy and
   standard-library SQLite. No new runtime package dependency.
3. Add bounded CPU jobs, immutable checkpoints, separate evaluations and inference.
4. Connect a lazy-loaded learning workspace to real records and operations.
5. Validate upload boundaries, split integrity, measured training, persistence,
   failure and concurrency semantics; build/lint and exercise browser flows.

The new module boundary prevents existing demo/reliability contracts from being
silently repurposed as evidence for newly trained engineering models. SQLite is
limited to this ML laboratory; mission storage and exports remain independent.

## Added architecture

```text
React OMNITorch workspace
  → /api/ml/v2 router
      → LabStore: image artifacts + immutable dataset/experiment records
      → LearningLab: one bounded CPU training worker
          → checkpoint registry
          → explicit evaluation
          → explicit inference
```

Storage defaults to `outputs/omnitorch/`, outside the source tree. The operator
can set `OMNITORCH_DATA_DIR` to a dedicated directory before launching FastAPI.
This is server configuration, never a client path. Each artifact uses a generated
32-character ID and a fixed server filename. SQLite records contain references
and SHA-256 digests; original names are sanitized display metadata only.

Image records preserve original bytes and inspect decoded format, dimensions,
source mode/channels, EXIF orientation, and pixel identity. PNG, JPEG and WebP
are accepted. Claimed MIME type must match decoded format. Upload bodies are
streamed with a 10 MiB bound; images above 16 million pixels, animated/multiframe
images, corrupt content and empty uploads are rejected.

Every image has separate `original`, `thumbnail.png` (at most 256×256), and
`rgb32.png` artifacts. Writes are exclusive and files become read-only. Original
and derived digests are verified on retrieval/use. This is application-level
immutability with integrity detection, not protection against a machine owner
who edits the database and files. Interrupted artifact writes can leave
unreferenced files; no collection or garbage collection policy exists yet.

`rgb32-v1` is intentionally one fixed preprocessing contract:

1. Apply EXIF orientation.
2. Composite alpha onto white and convert to RGB (no ICC color conversion).
3. Bilinear stretch to 32×32. This can distort aspect ratio.
4. Convert to float32 CHW with values divided by 255.

The image record stores this preprocessing contract alongside the Pillow version.
The original decoded dimensions/channels and the derived dimensions/channels
remain distinct. Dataset snapshots copy member IDs, labels (optional until
training), explicit split membership, source and image creation time, original,
canonical pixel and preprocessed hashes, and preprocessing configuration.
Snapshots receive their own ID, timestamp and manifest fingerprint. There is no
update/delete endpoint. A revised dataset requires a new snapshot.

Exact decoded-image duplicates cannot occur twice within a dataset, including
across splits. This does not detect near duplicates, scenes from the same video,
or the same object photographed differently. Operators must handle group-level
separation when curating real experiments.

## Training and model registry

`rgb_pool_mlp_v1` is a small classification baseline:
RGB → adaptive average pooling 8×8 → flatten 192 → linear 32 → ReLU → class logits.
It trains with cross entropy and SGD. It supports 2–32 classes, up to 512 images,
1–30 epochs, batches of 1–64, learning rates 0.00001–0.1, an explicit seed and CPU
execution. Train and validation splits must be nonempty and labeled; validation
labels must exist in training. Test data is never used in the training loop.

A request returns HTTP 202 and a persisted queued job. An in-process worker
records running/completed/failed states, real completed epochs, sample-weighted
training loss, validation loss/accuracy, configuration and timestamps. Work runs
outside the request event loop. A filesystem lock rejects concurrent training
requests (HTTP 409), including another process sharing the same store. A new
worker that acquires the lock marks leftover queued/running jobs failed after a
crash. The router closes the executor during application shutdown.

A cooperative 300-second limit is checked between batches. It is not a hard
process kill or security isolation; a hung native operation can exceed that
limit. Shutdown waits for the worker. No cancellation/resume or distributed
queue is implemented. Run one local backend service against each data directory. The v0.2 training worker currently uses POSIX file locking and is supported on Linux/WSL; native Windows worker locking is not implemented yet.

Model initialization preserves the process CPU RNG state; shuffling uses its
own seeded generator. Tests reproduce identical CPU weights and metrics in the
same environment. Cross-version/hardware bitwise equivalence is not promised.

A completed job publishes its model entry and job completion together in a
SQLite transaction after checkpoint creation. Failures register no selectable
model. Models include architecture, classes, dataset ID/fingerprint, training
configuration, validation metrics, CPU/PyTorch runtime, checkpoint reference and
hash, creation time and `trained` status. Checkpoints contain state dictionaries;
loading uses `weights_only=True` and `map_location="cpu"`. Clients cannot upload
checkpoints or select arbitrary architectures/paths.

## Evaluation and inference

Evaluation is a separate request, uses a selected model and dataset validation
or test split, and never changes a model record or weights. It persists sample
count, loss, accuracy, confusion matrix, ordered classes, split/configuration,
dataset fingerprint, checkpoint hash and timestamp. Test evaluation rejects
exact image overlap with the checkpoint's training **or validation** inputs;
validation evaluation rejects training overlap, including across snapshots.
Invalid evaluations return errors without creating a success record.

Inference explicitly selects a registry model ID and uploaded image ID. It
persists actual logits, softmax probabilities, predicted label, image/checkpoint
hashes, preprocessing, runtime and timestamp. Softmax scores are not calibrated
certainty or engineering validation. There is no automatic promotion and no
persistent global “active model”; the user selects a checkpoint in the workspace.

## API contract

Existing `/api/ml/*` demo and CAD-review endpoints remain compatible.
New endpoints are prefixed `/api/ml/v2`:

| Method / route | Request / result |
| --- | --- |
| POST `/images` | Raw image body, matching `Content-Type`, optional percent-encoded `X-Image-Name`; 201 image record |
| GET `/images/{id}/{original\|thumbnail\|preprocessed}` | Verified artifact bytes; originals download as attachments |
| POST `/datasets` | `{name, source, members:[{image_id,label,split}], preprocessing?}`; 201 snapshot |
| POST `/training` | `{dataset_id, epochs?, batch_size?, learning_rate?, seed?, architecture?, device?}`; 202 job |
| POST `/evaluations` | `{model_id,dataset_id,split}`; 201 evaluation |
| POST `/inferences` | `{model_id,image_id}`; 201 inference |
| GET `/{collection}` | `{items:[...]}` for images/datasets/jobs/models/evaluations/inferences |
| GET `/{collection}/{id}` | Persisted record |

Schemas reject unknown fields, malformed IDs and out-of-range configuration.
HTTP 413 means a resource size limit, 415 unsupported/mismatched image type,
422 invalid input, 404 missing record, and 409 worker busy/artifact integrity
failure. A failed asynchronous training operation is a job with `status=failed`
and an error, never a successful model. Collection responses are currently
unpaginated, so this version targets small local experiments.

## UX changes and boundaries

The console groups Mission, Engineering and Evidence destinations and retains
mission state across navigation. Hash routes identify the workspace and support
browser back/forward and direct links. Design/robotics/electronics destinations
open the relevant existing specialist report; they do not create new engines.
Artifacts retains Visual Bay, exports and dossier access. Keyboard navigation,
focus outlines, skip links and reduced motion are supported.

OMNITorch provides Data, Datasets, Train, Evaluate, Models and Inference views.
Training progress is polled while an active job exists; errors remain visible.
The workspace is loaded on demand. Its six views live in `frontend/src/components/omnitorch/`, with shared form/record primitives; the workspace container preserves draft configuration and selection across tabs. The legacy clothing demo remains under
Inference. Public capability copy distinguishes the new foundation from future
engineering applications.

Removed corner Idle/Online/Ready-style chrome, the permanent Local Link claim,
agent Ready fallback, graph review online/offline labels, Forge idle badge,
redundant dossier status pill and the ROS corner badge. Actual validation results and ROS process evidence remain. Removed the
scanline/pulsing graph decoration and the elapsed-time-generated mission stages
and intensity. The mission loader now states that stage telemetry is unavailable
and shows elapsed time while waiting for the backend result.

## Known limits and next milestone

This is a local-first classification foundation, not engineering-specific
recognition, defect detection, CAD understanding, segmentation, multimodal
learning, or learning from mission outcomes. Upload does not modify weights.
The repository's existing local service authentication/deployment model is
unchanged; do not treat this as a multi-user hosted data service.

Next milestone: a small, human-labeled engineering-image benchmark with group-aware
splits, class-balance checks, dataset pagination, run cancellation, held-out error
inspection, and an explicit evaluation-backed promotion policy. Only then extend
architectures or connect validated mission outcomes as dataset sources.
