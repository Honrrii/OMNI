"""OMNITorch v0.2 requests. IDs are opaque; clients cannot supply filesystem paths."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Identifier = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{32}$")]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Split = Literal["train", "validation", "test"]


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Preprocessing(StrictRequest):
    version: Literal["rgb32-v1"] = "rgb32-v1"
    width: Literal[32] = 32
    height: Literal[32] = 32
    channels: Literal[3] = 3
    exif_orientation: Literal["transpose"] = "transpose"
    alpha_background: Literal["white"] = "white"
    resize: Literal["bilinear-stretch"] = "bilinear-stretch"
    normalization: Literal["uint8/255"] = "uint8/255"


class DatasetMember(StrictRequest):
    image_id: Identifier
    label: Text | None = None
    split: Split


class DatasetRequest(StrictRequest):
    name: Text
    source: Text = "user-curated"
    members: list[DatasetMember] = Field(min_length=1, max_length=512)
    preprocessing: Preprocessing = Field(default_factory=Preprocessing)

    @model_validator(mode="after")
    def unique_images(self):
        ids = [member.image_id for member in self.members]
        if len(ids) != len(set(ids)):
            raise ValueError("An image may appear only once in a dataset snapshot.")
        return self


class TrainingRequest(StrictRequest):
    dataset_id: Identifier
    architecture: Literal["rgb_pool_mlp_v1"] = "rgb_pool_mlp_v1"
    epochs: int = Field(default=5, ge=1, le=30, strict=True)
    batch_size: int = Field(default=16, ge=1, le=64, strict=True)
    learning_rate: float = Field(default=0.01, ge=0.00001, le=0.1)
    seed: int = Field(default=42, ge=0, le=2**31 - 1, strict=True)
    device: Literal["cpu"] = "cpu"


class EvaluationRequest(StrictRequest):
    model_id: Identifier
    dataset_id: Identifier
    split: Literal["validation", "test"] = "test"


class InferenceRequest(StrictRequest):
    model_id: Identifier
    image_id: Identifier
