"""Real CPU integration tests with generated pixels; no downloads or mission calls."""
import io
import threading
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError
import torch

from backend.app.api.ml_lab_routes import get_lab, router
from backend.app.ml.lab_schemas import DatasetRequest, TrainingRequest, EvaluationRequest, InferenceRequest
from backend.app.ml.lab_service import LearningLab, build_model
from backend.app.ml.lab_store import LabError, LabStore, MAX_IMAGE_BYTES, digest


def image_bytes(color=(20, 30, 40), mode="RGB", size=(40, 24), format="PNG"):
    buffer = io.BytesIO()
    Image.new(mode, size, color).save(buffer, format=format)
    return buffer.getvalue()


@pytest.fixture
def lab(tmp_path):
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    instance = LearningLab(LabStore(tmp_path / "lab"))
    yield instance
    instance.close()
    torch.set_num_threads(previous)


@pytest.fixture
def client(lab):
    app = FastAPI()
    app.include_router(router, prefix="/api/ml/v2")
    app.dependency_overrides[get_lab] = lambda: lab
    with TestClient(app) as client:
        yield client


def dataset(lab):
    members = []
    for i, split in enumerate(["train", "validation", "test"]):
        for label, color in [("dark", (10 + i, 20, 30)), ("light", (240 - i, 230, 220))]:
            record = lab.store.intake(image_bytes(color), f"{label}-{i}.png", "image/png")
            members.append({"image_id": record["id"], "label": label, "split": split})
    return lab.store.create_dataset(DatasetRequest(name="Synthetic fixture", members=members))


def wait_job(lab, identity):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        job = lab.store.get("jobs", identity)
        if job["status"] in {"completed", "failed"}:
            return job
        time.sleep(.01)
    pytest.fail("Training worker did not finish within 20 seconds")


def trained(lab):
    data = dataset(lab)
    job = wait_job(lab, lab.submit(TrainingRequest(dataset_id=data["id"], epochs=2, seed=123))["id"])
    assert job["status"] == "completed", job
    return data, job


def test_intake_preserves_original_and_explicit_derivatives(client, lab):
    raw = image_bytes((10, 20, 30, 100), mode="RGBA")
    response = client.post("/api/ml/v2/images", content=raw, headers={"content-type": "image/png", "x-image-name": "../../evil.png"})
    assert response.status_code == 201
    record = response.json()
    assert record["filename"] == "evil.png"
    assert (record["width"], record["height"], record["channels"]) == (40, 24, 4)
    assert record["sha256"] == digest(raw)
    assert record["preprocessing"]["version"] == "rgb32-v1"
    assert lab.store.list("models") == lab.store.list("jobs") == []
    url = f'/api/ml/v2/images/{record["id"]}'
    original = client.get(f"{url}/original")
    assert original.content == raw
    assert original.headers["x-content-type-options"] == "nosniff"
    preview = client.get(f"{url}/preprocessed")
    with Image.open(io.BytesIO(preview.content)) as rendered:
        assert rendered.size == (32, 32) and rendered.mode == "RGB"
    second = lab.store.intake(raw, "copy.png", "image/png")
    assert second["preprocessed"]["sha256"] == record["preprocessed"]["sha256"]
    assert not lab.store.path("images", record["id"], "original").stat().st_mode & 0o222


@pytest.mark.parametrize("body,media,status", [(b"", "image/png", 422), (b"garbage", "image/png", 422),
    (b"<svg/>", "image/svg+xml", 415), (image_bytes(), "image/jpeg", 415),
    (image_bytes(format="GIF"), "image/png", 415), (b"x" * (MAX_IMAGE_BYTES + 1), "image/png", 413)])
def test_upload_rejections(client, lab, body, media, status):
    response = client.post("/api/ml/v2/images", content=body, headers={"content-type": media})
    assert response.status_code == status
    assert lab.store.list("images") == []


def test_pixel_limit_animation_and_truncation(lab, monkeypatch):
    monkeypatch.setattr("backend.app.ml.lab_store.MAX_IMAGE_PIXELS", 10)
    with pytest.raises(LabError, match="megapixels"):
        lab.store.intake(image_bytes(), "a.png", "image/png")
    monkeypatch.setattr("backend.app.ml.lab_store.MAX_IMAGE_PIXELS", 16_000_000)
    with pytest.raises(LabError, match="corrupt"):
        lab.store.intake(image_bytes()[:40], "a.png", "image/png")
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), "red").save(buffer, format="PNG", save_all=True, append_images=[Image.new("RGB", (10, 10), "blue")])
    with pytest.raises(LabError, match="multi-frame"):
        lab.store.intake(buffer.getvalue(), "a.png", "image/png")


def test_exif_orientation_and_transparency(lab):
    buffer = io.BytesIO()
    image = Image.new("RGB", (12, 24), "red")
    exif = image.getexif()
    exif[274] = 6
    image.save(buffer, format="JPEG", exif=exif)
    record = lab.store.intake(buffer.getvalue(), "rotated.jpg", "image/jpeg")
    assert record["thumbnail"]["width"] == 24 and record["thumbnail"]["height"] == 12
    transparent = lab.store.intake(image_bytes((255, 0, 0, 0), "RGBA"), "alpha.png", "image/png")
    assert torch.all(lab._image_tensor(transparent["id"]) == 1)


def test_dataset_snapshot_roundtrip_and_no_mutation(client, lab):
    data = dataset(lab)
    before = lab.store.get("datasets", data["id"])
    member = before["members"][0]
    assert member["sha256"] and member["source"] and member["image_created_at"]
    assert data["split_counts"] == {"train": 2, "validation": 2, "test": 2}
    assert client.patch(f'/api/ml/v2/datasets/{data["id"]}', json={"name": "changed"}).status_code == 405
    newer = lab.store.create_dataset(DatasetRequest(name="new version", members=[{k: m[k] for k in ("image_id", "label", "split")} for m in before["members"]]))
    assert newer["id"] != data["id"]
    assert lab.store.get("datasets", data["id"]) == before


def test_duplicates_and_client_paths_fail_closed(client, lab):
    a = lab.store.intake(image_bytes(), "one.png", "image/png")
    b = lab.store.intake(image_bytes(), "two.png", "image/png")
    with pytest.raises(LabError, match="Duplicate"):
        lab.store.create_dataset(DatasetRequest(name="leak", members=[{"image_id": a["id"], "split": "train"}, {"image_id": b["id"], "split": "test"}]))
    with pytest.raises(ValidationError):
        DatasetRequest(name="dup", members=[{"image_id": a["id"], "split": "train"}] * 2)
    for bad in ["../secrets", "/tmp/model.pt", "a" * 31, "Z" * 32]:
        response = client.post("/api/ml/v2/inferences", json={"model_id": bad, "image_id": a["id"]})
        assert response.status_code == 422
    assert client.post("/api/ml/v2/training", json={"dataset_id": a["id"], "checkpoint_path": "/tmp/x"}).status_code == 422
    assert client.get('/api/ml/v2/images/' + '0' * 32).status_code == 404


@pytest.mark.parametrize("configuration", [{"epochs": 0}, {"epochs": 31}, {"epochs": True}, {"batch_size": 65},
    {"learning_rate": float("nan")}, {"seed": -1}, {"architecture": "arbitrary"}, {"device": "cuda"}])
def test_training_schema_bounds(configuration):
    with pytest.raises(ValidationError):
        TrainingRequest(dataset_id="a" * 32, **configuration)


def test_training_requires_classes_labels_and_splits(lab):
    a = lab.store.intake(image_bytes(), "a.png", "image/png")
    b = lab.store.intake(image_bytes((22, 33, 44)), "b.png", "image/png")
    for members, message in [([{"image_id": a["id"], "split": "train"}], "nonempty"),
        ([{"image_id": a["id"], "split": "train"}, {"image_id": b["id"], "split": "validation"}], "label"),
        ([{"image_id": a["id"], "split": "train", "label": "a"}, {"image_id": b["id"], "split": "validation", "label": "a"}], "classes")]:
        data = lab.store.create_dataset(DatasetRequest(name="bad", members=members))
        with pytest.raises(LabError, match=message):
            lab.submit(TrainingRequest(dataset_id=data["id"]))
    assert not lab.store.list("jobs")


def test_real_train_evaluate_infer_and_restart(client, lab):
    data = dataset(lab)
    response = client.post("/api/ml/v2/training", json={"dataset_id": data["id"], "epochs": 2, "seed": 123})
    assert response.status_code == 202
    job = wait_job(lab, response.json()["id"])
    assert job["status"] == "completed", job
    assert job["epoch"] == 2 and len(job["history"]) == 2
    model_record, model = lab._load_checkpoint(job["model_id"])
    initial = build_model(2, 123)
    assert any(not torch.equal(v, initial.state_dict()[k]) for k, v in model.state_dict().items())
    assert model_record["configuration"]["seed"] == 123
    assert not lab.store.list("evaluations")
    model_before = lab.store.get("models", job["model_id"])
    result = client.post("/api/ml/v2/evaluations", json={"model_id": job["model_id"], "dataset_id": data["id"], "split": "test"})
    assert result.status_code == 201, result.text
    metrics = result.json()["metrics"]
    assert metrics["sample_count"] == 2 and sum(map(sum, metrics["confusion_matrix"])) == 2
    image_id = data["members"][-1]["image_id"]
    result = client.post("/api/ml/v2/inferences", json={"model_id": job["model_id"], "image_id": image_id})
    assert result.status_code == 201, result.text
    assert sum(o["probability"] for o in result.json()["outputs"]) == pytest.approx(1)
    assert lab.store.get("models", job["model_id"]) == model_before
    reopened = LabStore(lab.store.root)
    assert reopened.get("datasets", data["id"]) == data
    assert reopened.get("inferences", result.json()["id"])["prediction"] in {"dark", "light"}


def test_seed_reproduces_metrics_and_predictions(lab):
    data, first = trained(lab)
    second = wait_job(lab, lab.submit(TrainingRequest(dataset_id=data["id"], epochs=2, seed=123))["id"])
    assert first["history"] == second["history"]
    _, first_model = lab._load_checkpoint(first["model_id"])
    _, second_model = lab._load_checkpoint(second["model_id"])
    assert all(torch.equal(value, second_model.state_dict()[key]) for key, value in first_model.state_dict().items())


def test_failed_training_never_registers_model(lab, monkeypatch):
    data = dataset(lab)
    def fail(*args):
        raise RuntimeError("synthetic failure")
    monkeypatch.setattr(lab, "_split", fail)
    job = wait_job(lab, lab.submit(TrainingRequest(dataset_id=data["id"]))["id"])
    assert job["status"] == "failed" and job["model_id"] is None
    assert "RuntimeError" in job["error"] and not lab.store.list("models")


def test_training_runtime_limit(lab, monkeypatch):
    data = dataset(lab)
    monkeypatch.setattr("backend.app.ml.lab_service.MAX_TRAIN_SECONDS", -1)
    job = wait_job(lab, lab.submit(TrainingRequest(dataset_id=data["id"]))["id"])
    assert job["status"] == "failed" and "runtime limit" in job["error"]
    assert not lab.store.list("models")


def test_single_worker_and_interrupted_recovery(lab, monkeypatch):
    data = dataset(lab)
    entered, release = threading.Event(), threading.Event()
    original = lab._split
    def hold(*args):
        entered.set()
        assert release.wait(10)
        return original(*args)
    monkeypatch.setattr(lab, "_split", hold)
    job = lab.submit(TrainingRequest(dataset_id=data["id"], epochs=1))
    assert entered.wait(5)
    other = LearningLab(LabStore(lab.store.root))
    try:
        with pytest.raises(LabError, match="already running"):
            other.submit(TrainingRequest(dataset_id=data["id"]))
        assert other.store.get("jobs", job["id"])["status"] == "running"
    finally:
        release.set()
        other.close()
    assert wait_job(lab, job["id"])["status"] == "completed"
    stale = {**job, "id": "f" * 32, "status": "running"}
    lab.store.put("jobs", stale)
    recovered = LearningLab(LabStore(lab.store.root))
    try:
        assert recovered.store.get("jobs", stale["id"])["status"] == "failed"
    finally:
        recovered.close()


def test_evaluation_rejects_leakage_unknown_labels_and_missing_artifacts(lab):
    data, job = trained(lab)
    leaked = lab.store.create_dataset(DatasetRequest(name="leak", members=[{"image_id": data["members"][0]["image_id"], "label": "dark", "split": "test"}]))
    with pytest.raises(LabError, match="overlaps"):
        lab.evaluate(EvaluationRequest(model_id=job["model_id"], dataset_id=leaked["id"]))
    unseen = lab.store.create_dataset(DatasetRequest(name="unknown", members=[{"image_id": data["members"][-1]["image_id"], "label": "unseen", "split": "test"}]))
    with pytest.raises(LabError, match="known"):
        lab.evaluate(EvaluationRequest(model_id=job["model_id"], dataset_id=unseen["id"]))
    path = lab.store.path("models", job["model_id"], "checkpoint.pt")
    path.chmod(0o644)
    path.write_bytes(b"tampered")
    with pytest.raises(LabError, match="integrity"):
        lab.infer(InferenceRequest(model_id=job["model_id"], image_id=data["members"][0]["image_id"]))
    path.unlink()
    with pytest.raises(LabError, match="missing"):
        lab._load_checkpoint(job["model_id"])


def test_legacy_demo_remains_real():
    from backend.app.ml.omnitorch_service import analyze_image
    result = analyze_image(image_bytes())
    assert result.model_name == "fashion_mnist_mlp"
    assert result.status == "ok" and 0 <= result.prediction.confidence <= 1
