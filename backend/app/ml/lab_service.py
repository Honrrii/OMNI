"""Bounded, local CPU classification experiments. Upload never triggers learning."""
from concurrent.futures import ThreadPoolExecutor
import fcntl
import io
import json
import math
import threading
import time

import numpy as np
from PIL import Image
import torch
from torch import nn

from .lab_schemas import TrainingRequest, EvaluationRequest, InferenceRequest
from .lab_store import LabError, LabStore, new_id, now

MAX_TRAIN_SECONDS = 300
_RNG_LOCK = threading.Lock()


def build_model(classes, seed=0):
    # Restore the process RNG after construction. Batch shuffling has its own generator.
    with _RNG_LOCK, torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(seed)
        return nn.Sequential(nn.AdaptiveAvgPool2d((8, 8)), nn.Flatten(),
                             nn.Linear(3 * 8 * 8, 32), nn.ReLU(), nn.Linear(32, classes))


class LearningLab:
    def __init__(self, store: LabStore):
        self.store = store
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="omnitorch")
        # A filesystem lock also prevents another process using this store from training.
        lock = self._acquire_worker(required=False)
        if lock:
            try:
                self._recover_interrupted()
            finally:
                lock.close()

    def close(self):
        self.executor.shutdown(wait=True)

    def _acquire_worker(self, required=True):
        lock = (self.store.root / "training.lock").open("a")
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock.close()
            if required:
                raise LabError("A training job is already running. Wait for it to finish.", 409)
            return None
        return lock

    def _recover_interrupted(self):
        for job in self.store.list("jobs"):
            if job["status"] in {"queued", "running"}:
                job.update(status="failed", error="Training was interrupted before completion. Submit a new run.", completed_at=now())
                self.store.put("jobs", job, update_job=True)

    def _training_dataset(self, identity):
        dataset = self.store.get("datasets", identity)
        training = [m for m in dataset["members"] if m["split"] == "train"]
        validation = [m for m in dataset["members"] if m["split"] == "validation"]
        if not training or not validation:
            raise LabError("Training requires nonempty train and validation splits.")
        if any(m["label"] is None for m in training + validation):
            raise LabError("Every train and validation image needs a label.")
        classes = sorted({m["label"] for m in training})
        if not 2 <= len(classes) <= 32:
            raise LabError("Training requires between 2 and 32 classes in the train split.")
        if any(m["label"] not in classes for m in validation):
            raise LabError("Validation labels must exist in the train split.")
        return dataset, classes

    def submit(self, request: TrainingRequest):
        dataset, classes = self._training_dataset(request.dataset_id)
        lock = self._acquire_worker()
        try:
            self._recover_interrupted()
            job = {"id": new_id(), "created_at": now(), "status": "queued", "epoch": 0,
                   "history": [], "configuration": request.model_dump(), "classes": classes,
                   "dataset_id": dataset["id"], "dataset_fingerprint": dataset["fingerprint"],
                   "architecture": request.architecture, "model_id": None, "error": None}
            self.store.put("jobs", job)
            self.executor.submit(self._run_training, job, dataset, lock)
        except Exception:
            lock.close()
            raise
        return job

    def _image_tensor(self, identity, expected_sha=None):
        record = self.store.get("images", identity)
        data = self.store.read_artifact("images", identity, "rgb32.png", expected_sha or record["preprocessed"]["sha256"])
        with Image.open(io.BytesIO(data)) as image:
            array = np.array(image, dtype=np.float32) / 255.0
        return torch.from_numpy(array).permute(2, 0, 1)

    def _split(self, dataset, split, classes):
        members = [m for m in dataset["members"] if m["split"] == split]
        if not members:
            raise LabError(f"The {split} split is empty.")
        if any(m["label"] not in classes for m in members):
            raise LabError("Every evaluated image must have a label known to the checkpoint.")
        x = torch.stack([self._image_tensor(m["image_id"], m["preprocessed_sha256"]) for m in members])
        y = torch.tensor([classes.index(m["label"]) for m in members], dtype=torch.long)
        return x, y

    @staticmethod
    def _metrics(model, x, y, class_count):
        model.eval()
        with torch.inference_mode():
            logits = model(x)
            loss = nn.functional.cross_entropy(logits, y).item()
            if not math.isfinite(loss):
                raise LabError("Non-finite model output; the operation failed.")
            predictions = logits.argmax(dim=1)
            confusion = torch.bincount(y * class_count + predictions, minlength=class_count**2).reshape(class_count, class_count)
        return {"loss": loss, "accuracy": (predictions == y).float().mean().item(),
                "sample_count": len(y), "confusion_matrix": confusion.tolist()}

    def _run_training(self, initial_job, dataset, lock):
        job = dict(initial_job)
        started = time.monotonic()
        try:
            job.update(status="running", started_at=now())
            self.store.put("jobs", job, update_job=True)
            config, classes = job["configuration"], job["classes"]
            model = build_model(len(classes), config["seed"])
            x, y = self._split(dataset, "train", classes)
            vx, vy = self._split(dataset, "validation", classes)
            optimizer = torch.optim.SGD(model.parameters(), lr=config["learning_rate"])
            generator = torch.Generator().manual_seed(config["seed"])
            for epoch in range(1, config["epochs"] + 1):
                model.train()
                order = torch.randperm(len(y), generator=generator)
                total_loss = 0.0
                for indices in order.split(config["batch_size"]):
                    if time.monotonic() - started > MAX_TRAIN_SECONDS:
                        raise LabError("Training exceeded the 300 second runtime limit.")
                    optimizer.zero_grad()
                    loss = nn.functional.cross_entropy(model(x[indices]), y[indices])
                    if not torch.isfinite(loss):
                        raise LabError("Training produced a non-finite loss.")
                    loss.backward()
                    optimizer.step()
                    total_loss += loss.item() * len(indices)
                metrics = self._metrics(model, vx, vy, len(classes))
                job["history"].append({"epoch": epoch, "loss": total_loss / len(y),
                                       "validation_loss": metrics["loss"], "validation_accuracy": metrics["accuracy"]})
                job["epoch"] = epoch
                self.store.put("jobs", job, update_job=True)
            model_id = new_id()
            buffer = io.BytesIO()
            torch.save(model.state_dict(), buffer)
            checkpoint = self.store.write_artifact("models", model_id, "checkpoint.pt", buffer.getvalue())
            entry = {"id": model_id, "created_at": now(), "status": "trained", "architecture": config["architecture"],
                     "dataset_id": dataset["id"], "dataset_fingerprint": dataset["fingerprint"], "job_id": job["id"],
                     "configuration": config, "preprocessing": dataset["preprocessing"], "classes": classes,
                     "metrics": {"validation": metrics}, "checkpoint": checkpoint,
                     "torch_version": str(torch.__version__), "device": "cpu",
                     "architecture_detail": "RGB → average pool 8×8 → flatten 192 → linear 32 → ReLU → class logits"}
            job.update(status="completed", completed_at=now(), model_id=model_id)
            # A model becomes selectable only when its checkpoint and completed job exist.
            with self.store.connect() as db:
                db.execute("INSERT INTO records VALUES ('models', ?, ?)", (model_id, json.dumps(entry, allow_nan=False)))
                db.execute("UPDATE records SET body=? WHERE kind='jobs' AND id=?", (json.dumps(job, allow_nan=False), job["id"]))
        except Exception as exc:
            job.update(status="failed", completed_at=now(), model_id=None,
                       error=str(exc) if isinstance(exc, LabError) else f"Training failed ({type(exc).__name__}). No model was registered.")
            self.store.put("jobs", job, update_job=True)
        finally:
            lock.close()

    def _load_checkpoint(self, identity):
        record = self.store.get("models", identity)
        data = self.store.read_artifact("models", identity, "checkpoint.pt", record["checkpoint"]["sha256"])
        model = build_model(len(record["classes"]))
        try:
            model.load_state_dict(torch.load(io.BytesIO(data), map_location="cpu", weights_only=True))
        except Exception as exc:
            raise LabError("The registered checkpoint could not be loaded.", 409) from exc
        model.eval()
        return record, model

    def evaluate(self, request: EvaluationRequest):
        record, model = self._load_checkpoint(request.model_id)
        dataset = self.store.get("datasets", request.dataset_id)
        if dataset["preprocessing"] != record["preprocessing"]:
            raise LabError("Dataset preprocessing does not match the checkpoint.")
        # New snapshots must not accidentally re-label training/validation images as held-out test data.
        original = self.store.get("datasets", record["dataset_id"])
        used_splits = {"train", "validation"} if request.split == "test" else {"train"}
        used = {m["pixel_sha256"] for m in original["members"] if m["split"] in used_splits}
        if any(m["pixel_sha256"] in used for m in dataset["members"] if m["split"] == request.split):
            raise LabError("Evaluation split overlaps data used to train or select this checkpoint.")
        x, y = self._split(dataset, request.split, record["classes"])
        metrics = self._metrics(model, x, y, len(record["classes"]))
        return self.store.put("evaluations", {"id": new_id(), "created_at": now(), "status": "completed",
                              "configuration": request.model_dump(), "dataset_fingerprint": dataset["fingerprint"],
                              "checkpoint_sha256": record["checkpoint"]["sha256"], "classes": record["classes"],
                              "confusion_axes": "rows=actual, columns=predicted", "metrics": metrics})

    def infer(self, request: InferenceRequest):
        record, model = self._load_checkpoint(request.model_id)
        image = self.store.get("images", request.image_id)
        started = time.perf_counter()
        with torch.inference_mode():
            logits = model(self._image_tensor(request.image_id).unsqueeze(0))[0]
            if not torch.isfinite(logits).all():
                raise LabError("Checkpoint produced non-finite output.")
            probabilities = logits.softmax(dim=0).tolist()
        return self.store.put("inferences", {"id": new_id(), "created_at": now(), "status": "completed",
                              "configuration": request.model_dump(), "image_sha256": image["sha256"],
                              "checkpoint_sha256": record["checkpoint"]["sha256"], "preprocessing": record["preprocessing"],
                              "prediction": record["classes"][int(logits.argmax())],
                              "outputs": [{"label": label, "logit": logit, "probability": probability}
                                          for label, logit, probability in zip(record["classes"], logits.tolist(), probabilities)],
                              "device": "cpu", "inference_ms": (time.perf_counter() - started) * 1000,
                              "interpretation": "Classifier scores for the trained labels; not calibrated certainty or engineering validation."})
