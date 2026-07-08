from __future__ import annotations

from io import BytesIO
from typing import Any, Dict

import numpy as np
from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError


def _load_image(image_bytes: bytes) -> Image.Image:
    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
    except UnidentifiedImageError as exc:
        raise ValueError("Uploaded file is not a readable image.") from exc

    if image.width < 20 or image.height < 20:
        raise ValueError("Image is too small for CAD visual review.")

    return image


def _edge_density(gray: Image.Image) -> float:
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_array = np.asarray(edges, dtype=np.float32) / 255.0
    return float(np.mean(edge_array > 0.18))


def _foreground_mask(gray: Image.Image) -> np.ndarray:
    arr = np.asarray(gray, dtype=np.float32) / 255.0

    # CAD screenshots often have:
    # - light grid/background
    # - darker shaded model geometry
    #
    # This threshold is intentionally conservative so thin grid lines
    # are less likely to become foreground.
    dark_geometry_mask = arr < 0.62

    # If the mask is too small, relax threshold slightly.
    if dark_geometry_mask.mean() < 0.02:
        dark_geometry_mask = arr < 0.72

    # If the mask is too large, tighten threshold.
    if dark_geometry_mask.mean() > 0.65:
        dark_geometry_mask = arr < 0.50

    return dark_geometry_mask

def _trim_sparse_rows_and_cols(mask: np.ndarray) -> np.ndarray:
    """
    Remove sparse grid/background rows and columns from the mask.

    This helps prevent Fusion 360 grid lines from making the bounding box
    cover the entire screenshot.
    """
    if mask.size == 0:
        return mask

    row_density = mask.mean(axis=1)
    col_density = mask.mean(axis=0)

    row_keep = row_density > 0.015
    col_keep = col_density > 0.015

    cleaned = mask.copy()

    cleaned[~row_keep, :] = False
    cleaned[:, ~col_keep] = False

    return cleaned


def _bounding_box_metrics(mask: np.ndarray) -> Dict[str, Any]:
    ys, xs = np.where(mask)

    if len(xs) == 0 or len(ys) == 0:
        return {
            "has_foreground": False,
            "bbox_width_ratio": 0.0,
            "bbox_height_ratio": 0.0,
            "aspect_ratio": 0.0,
            "vertical_coverage": 0.0,
            "horizontal_coverage": 0.0,
        }

    height, width = mask.shape

    min_x, max_x = int(xs.min()), int(xs.max())
    min_y, max_y = int(ys.min()), int(ys.max())

    bbox_width = max_x - min_x + 1
    bbox_height = max_y - min_y + 1

    bbox_width_ratio = bbox_width / width
    bbox_height_ratio = bbox_height / height
    aspect_ratio = bbox_width / max(bbox_height, 1)

    return {
        "has_foreground": True,
        "bbox_width_ratio": round(bbox_width_ratio, 4),
        "bbox_height_ratio": round(bbox_height_ratio, 4),
        "aspect_ratio": round(aspect_ratio, 4),
        "vertical_coverage": round(bbox_height_ratio, 4),
        "horizontal_coverage": round(bbox_width_ratio, 4),
        "bbox": {
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
        },
    }


def _estimate_flatness(metrics: Dict[str, Any], edge_density: float) -> Dict[str, Any]:
    aspect_ratio = metrics.get("aspect_ratio", 0.0)
    vertical_coverage = metrics.get("vertical_coverage", 0.0)

    flatness_score = 0.0

    if aspect_ratio > 2.8:
        flatness_score += 0.45
    elif aspect_ratio > 2.0:
        flatness_score += 0.30
    elif aspect_ratio > 1.5:
        flatness_score += 0.15

    if vertical_coverage < 0.28:
        flatness_score += 0.35
    elif vertical_coverage < 0.40:
        flatness_score += 0.20

    if edge_density < 0.035:
        flatness_score += 0.20

    flatness_score = min(1.0, flatness_score)

    if flatness_score >= 0.65:
        estimated_3d_structure = "low"
    elif flatness_score >= 0.35:
        estimated_3d_structure = "moderate"
    else:
        estimated_3d_structure = "higher"

    return {
        "flatness_score": round(flatness_score, 4),
        "flatness_warning": flatness_score >= 0.50,
        "estimated_3d_structure": estimated_3d_structure,
    }


def _recommendations(review: Dict[str, Any]) -> list[str]:
    recommendations: list[str] = []

    if review["flatness_warning"]:
        recommendations.append(
            "Increase vertical separation between major CAD components instead of placing all geometry on one base plane."
        )

    if review["estimated_3d_structure"] == "low":
        recommendations.append(
            "Add elevated body segments, raised sensor mounts, or stacked mechanical layers to improve 3D morphology."
        )

    if review["geometry_metrics"]["aspect_ratio"] > 2.0:
        recommendations.append(
            "The visible geometry appears wide relative to its height; consider a taller body hierarchy or more pronounced vertical features."
        )

    if review["edge_density"] < 0.035:
        recommendations.append(
            "The screenshot has low edge density; add clearer component boundaries, mounting bosses, legs, wheels, brackets, or structural features."
        )

    if review.get("planar_morphology_warning"):
        recommendations.append(
            "The design has a broad planar footprint. Add raised modules, stacked body layers, sensor towers, ribs, or clearer vertical structure."
        )

    if not recommendations:
        recommendations.append(
            "No severe flatness warning detected. Continue validating dimensions, manufacturability, joints, and physical feasibility."
        )

    return recommendations


def review_cad_image(image_bytes: bytes) -> Dict[str, Any]:
    """
    Rule-based CAD screenshot review.

    This is not a trained CAD model yet. It estimates visual flatness and
    morphology risk from screenshot-level image features.
    """
    image = _load_image(image_bytes)

    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)

    mask = _foreground_mask(gray)
    mask = _trim_sparse_rows_and_cols(mask)
    bbox_metrics = _bounding_box_metrics(mask)
    edges = _edge_density(gray)

    if not bbox_metrics["has_foreground"]:
        return {
            "system": "OMNITorch",
            "task_type": "cad_visual_review",
            "status": "WARN",
            "visual_review": {
                "flatness_warning": True,
                "flatness_score": 1.0,
                "estimated_3d_structure": "unknown",
                "edge_density": round(edges, 4),
                "geometry_metrics": bbox_metrics,
                "recommendations": [
                    "Could not detect clear foreground CAD geometry. Upload a clearer screenshot with the model centered."
                ],
            },
            "human_review_required": True,
        }

    flatness = _estimate_flatness(bbox_metrics, edges)

    aspect_ratio = bbox_metrics.get("aspect_ratio", 0.0)
    edge_density_value = round(edges, 4)

    planar_morphology_warning = (
    aspect_ratio > 1.55
    and edge_density_value > 0.06
    and not flatness["flatness_warning"]
    )

    visual_review = {
    **flatness,
    "planar_morphology_warning": planar_morphology_warning,
    "edge_density": edge_density_value,
    "geometry_metrics": bbox_metrics,
    }

    visual_review["recommendations"] = _recommendations(visual_review)

    status = (
    "WARN"
    if visual_review["flatness_warning"] or visual_review["planar_morphology_warning"]
    else "PASS"
    )

    return {
        "system": "OMNITorch",
        "task_type": "cad_visual_review",
        "status": status,
        "visual_review": visual_review,
        "omni_interpretation": {
            "summary": (
                "CAD visual review detected a flatness risk."
                if visual_review["flatness_warning"]
                else (
                        "CAD visual review detected a broad planar morphology risk."
                        if visual_review["planar_morphology_warning"]
                        else "CAD visual review did not detect a severe flatness risk."
                    )
            ),
            "engineering_relevance": (
                "This review helps OMNI identify CAD concepts that may be too planar, too flat, "
                "or lacking visible 3D morphology before accepting them as realistic designs."
            ),
            "limitations": (
                "This is a rule-based screenshot heuristic, not a true CAD geometry parser or trained morphology model."
            ),
            "next_step": (
                "Use these warnings to revise Fusion 360 generation constraints and then re-review the updated screenshot."
            ),
        },
        "human_review_required": True,
    }