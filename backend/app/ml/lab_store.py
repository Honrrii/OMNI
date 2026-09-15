"""Local immutable image/dataset records and explicit derived artifacts.

SQLite publishes records transactionally after their artifacts exist. The only
mutable records are training jobs. No update/delete route exists for datasets,
images, evaluations or models. Originals are byte-for-byte preserved.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
from datetime import datetime, timezone
import uuid
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError, __version__ as pillow_version

from .lab_schemas import DatasetRequest, Preprocessing

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
KINDS = {"images", "datasets", "jobs", "models", "evaluations", "inferences"}


def now():
    return datetime.now(timezone.utc).isoformat()


def new_id():
    return uuid.uuid4().hex


def digest(data):
    return hashlib.sha256(data).hexdigest()


class LabError(Exception):
    def __init__(self, detail, status=422):
        super().__init__(detail)
        self.status = status


class LabStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS records (
                kind TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
                PRIMARY KEY (kind, id))""")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.root / "registry.sqlite3", timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    def path(self, kind, identity, filename):
        if kind not in KINDS or not re.fullmatch(r"[a-f0-9]{32}", identity):
            raise LabError("Invalid record identity.", 404)
        if filename not in {"original", "thumbnail.png", "rgb32.png", "checkpoint.pt"}:
            raise LabError("Unknown artifact.", 404)
        path = self.root / kind / identity / filename
        if not path.resolve().is_relative_to(self.root):
            raise LabError("Invalid artifact location.", 404)
        return path

    def get(self, kind, identity):
        if kind not in KINDS or not re.fullmatch(r"[a-f0-9]{32}", identity):
            raise LabError("Invalid record identity.", 404)
        with self.connect() as db:
            row = db.execute("SELECT body FROM records WHERE kind=? AND id=?", (kind, identity)).fetchone()
        if row is None:
            raise LabError(f"{kind.rstrip('s').capitalize()} record not found.", 404)
        return json.loads(row[0])

    def list(self, kind):
        if kind not in KINDS:
            raise LabError("Unknown collection.", 404)
        with self.connect() as db:
            rows = db.execute("SELECT body FROM records WHERE kind=? ORDER BY rowid DESC", (kind,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def put(self, kind, record, *, update_job=False):
        body = json.dumps(record, allow_nan=False)
        with self.connect() as db:
            if update_job:
                if kind != "jobs":
                    raise ValueError("Only job progress can be updated.")
                db.execute("UPDATE records SET body=? WHERE kind='jobs' AND id=?", (body, record["id"]))
            else:
                db.execute("INSERT INTO records VALUES (?, ?, ?)", (kind, record["id"], body))
        return record

    def write_artifact(self, kind, identity, filename, data):
        path = self.path(kind, identity, filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
        path.chmod(0o444)
        return {"sha256": digest(data), "bytes": len(data), "filename": filename}

    def read_artifact(self, kind, identity, filename, sha256):
        try:
            data = self.path(kind, identity, filename).read_bytes()
        except OSError as exc:
            raise LabError("A referenced artifact is missing or unreadable.", 409) from exc
        if digest(data) != sha256:
            raise LabError("Artifact integrity check failed.", 409)
        return data

    def intake(self, data: bytes, filename: str, content_type: str, source="user-upload"):
        if not data:
            raise LabError("The upload is empty.")
        if len(data) > MAX_IMAGE_BYTES:
            raise LabError("Maximum image size is 10 MiB.", 413)
        if content_type not in FORMATS.values():
            raise LabError("Upload a PNG, JPEG or WebP image.", 415)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as raw:
                    if raw.format not in FORMATS or FORMATS[raw.format] != content_type:
                        raise LabError("Decoded image type does not match the declared type.", 415)
                    if raw.width * raw.height > MAX_IMAGE_PIXELS:
                        raise LabError("Maximum decoded image size is 16 megapixels.", 413)
                    if getattr(raw, "n_frames", 1) != 1:
                        raise LabError("Animated or multi-frame images are not supported.")
                    metadata = {"width": raw.width, "height": raw.height, "mode": raw.mode,
                                "channels": len(raw.getbands()), "format": raw.format}
                    raw.verify()
                with Image.open(io.BytesIO(data)) as raw:
                    oriented = ImageOps.exif_transpose(raw).convert("RGBA")
                    background = Image.new("RGBA", oriented.size, "white")
                    rgb = Image.alpha_composite(background, oriented).convert("RGB")
        except LabError:
            raise
        except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
            raise LabError("Decoded image exceeds safe dimensions.", 413) from exc
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
            raise LabError("The image is corrupt or cannot be decoded.") from exc

        identity = new_id()
        # Filename is display-only and never used to construct a storage path.
        safe_name = re.sub(r"[^\w. -]", "_", filename.replace("\\", "/").rsplit("/", 1)[-1])[:120] or "image"
        record = {"id": identity, "created_at": now(), "source": source, "filename": safe_name,
                  "media_type": content_type, **metadata, "sha256": digest(data),
                  "pixel_sha256": digest(str(rgb.size).encode() + rgb.tobytes()),
                  "preprocessing": Preprocessing().model_dump(), "pillow_version": pillow_version}
        record["original"] = self.write_artifact("images", identity, "original", data)
        for name, rendered in [("thumbnail", rgb.copy()), ("preprocessed", rgb.resize((32, 32), Image.Resampling.BILINEAR))]:
            if name == "thumbnail":
                rendered.thumbnail((256, 256), Image.Resampling.BILINEAR)
            buffer = io.BytesIO()
            rendered.save(buffer, format="PNG")
            artifact_name = "thumbnail.png" if name == "thumbnail" else "rgb32.png"
            record[name] = {**self.write_artifact("images", identity, artifact_name, buffer.getvalue()),
                            "width": rendered.width, "height": rendered.height, "channels": 3}
        return self.put("images", record)

    def create_dataset(self, request: DatasetRequest):
        members, hashes = [], set()
        for member in request.members:
            image = self.get("images", member.image_id)
            if image["pixel_sha256"] in hashes:
                raise LabError("Duplicate image content is not allowed in a dataset, including across splits.")
            hashes.add(image["pixel_sha256"])
            members.append({**member.model_dump(), "sha256": image["sha256"],
                            "pixel_sha256": image["pixel_sha256"], "source": image["source"],
                            "image_created_at": image["created_at"],
                            "preprocessed_sha256": image["preprocessed"]["sha256"]})
        snapshot = {**request.model_dump(), "members": members}
        return self.put("datasets", {**snapshot, "id": new_id(), "created_at": now(),
                       "fingerprint": digest(json.dumps(snapshot, sort_keys=True).encode()),
                       "split_counts": {s: sum(m["split"] == s for m in members) for s in ("train", "validation", "test")}})


def default_root():
    # This is operator configuration, never request data.
    return Path(os.environ.get("OMNITORCH_DATA_DIR", Path(__file__).resolve().parents[3] / "outputs" / "omnitorch"))
