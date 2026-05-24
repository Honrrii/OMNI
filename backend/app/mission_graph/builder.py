"""
Mission Knowledge Graph v0.1 — builder.

Reads a harness-produced (or legacy) mission folder and returns a
MissionKnowledgeGraph.  All file I/O is defensive: missing or malformed
files produce ConsistencyWarnings rather than exceptions.

Public API:
    graph = build_graph(Path("outputs/omni_missions/2026-05-23_..."))
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from backend.app.mission_graph.schemas import (
    BodyRegion,
    CadFeature,
    Component,
    ConsistencyWarning,
    DataBus,
    GeneratedFile,
    MissionKnowledgeGraph,
    Morphology,
    PhysicsSubsystem,
    PowerRail,
    ProvenanceRef,
    Requirement,
    Ros2Node,
    Ros2Topic,
    ValidationCheck,
)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

_VOLT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[Vv](?:olt)?")

_KNOWN_PROTOCOLS = [
    "I2C", "SPI", "UART", "CAN", "USB", "GPIO", "RS485",
    "PWM", "Ethernet", "Wi-Fi", "Bluetooth", "MQTT",
]

_PLATFORM_KEYWORDS = [
    "manta ray", "insect robot", "hexapod", "quadruped",
    "robot arm", "humanoid", "drone", "uav", "auv", "rov", "rover",
]

_EXT_TO_TYPE: Dict[str, str] = {
    ".py":    "ros2",
    ".yaml":  "config",
    ".yml":   "config",
    ".json":  "artifact",
    ".csv":   "artifact",
    ".md":    "markdown",
    ".urdf":  "ros2",
    ".sdf":   "ros2",
    ".launch":"ros2",
    ".kicad_pcb": "kicad",
    ".f3d":   "fusion360",
    ".step":  "cad",
}


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower().strip()).strip("_") or "unknown"


def _load_json(path: Path) -> Tuple[Any, Optional[str]]:
    """Return (data, error_message). data is None on failure."""
    try:
        return json.loads(path.read_text("utf-8")), None
    except FileNotFoundError:
        return None, f"File not found: {path.name}"
    except json.JSONDecodeError as exc:
        return None, f"JSON decode error in {path.name}: {exc}"
    except Exception as exc:  # noqa: BLE001
        return None, f"Error reading {path.name}: {type(exc).__name__}: {exc}"


def _safe_list(val: Any) -> list:
    return val if isinstance(val, list) else []


def _safe_dict(val: Any) -> dict:
    return val if isinstance(val, dict) else {}


def _safe_str(val: Any) -> str:
    return str(val) if val is not None else ""


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def _extract_platform(mission_text: str) -> str:
    lower = mission_text.lower()
    for kw in sorted(_PLATFORM_KEYWORDS, key=len, reverse=True):
        if kw in lower:
            return kw
    return ""


def _extract_ros2(sky: dict) -> Tuple[List[Ros2Node], List[Ros2Topic]]:
    ros2_plan = _safe_dict(sky.get("ros2_package_plan"))
    raw_nodes = _safe_list(ros2_plan.get("nodes"))
    raw_topics = _safe_list(ros2_plan.get("topics"))  # list of name strings

    # Build topic name → id map first so nodes can reference by id.
    topic_name_to_id: Dict[str, str] = {}
    topics: List[Ros2Topic] = []
    for name in raw_topics:
        name_str = _safe_str(name).strip()
        if not name_str:
            continue
        tid = f"topic.{_slugify(name_str)}"
        if tid in topic_name_to_id.values():
            # Collision: append counter
            tid = f"{tid}_{len(topics):03d}"
        topic_name_to_id[name_str] = tid
        topics.append(Ros2Topic(id=tid, name=name_str))

    # Build nodes, and back-fill publisher/subscriber ids onto topics.
    topic_id_map: Dict[str, Ros2Topic] = {t.id: t for t in topics}
    nodes: List[Ros2Node] = []
    for raw in raw_nodes:
        if not isinstance(raw, dict):
            continue
        name_str = _safe_str(raw.get("name")).strip()
        if not name_str:
            continue
        node_id = f"node.{_slugify(name_str)}"
        pub_names = _safe_list(raw.get("publishes_to"))
        sub_names = _safe_list(raw.get("subscribes_to"))
        nodes.append(
            Ros2Node(
                id=node_id,
                name=name_str,
                purpose=_safe_str(raw.get("purpose")),
                publishes_to=[_safe_str(t) for t in pub_names],
                subscribes_to=[_safe_str(t) for t in sub_names],
                services=_safe_list(raw.get("services")),
                parameters=_safe_list(raw.get("parameters")),
            )
        )
        # Wire cross-references onto topics.
        for tname in pub_names:
            tid = topic_name_to_id.get(_safe_str(tname))
            if tid and tid in topic_id_map:
                topic_id_map[tid].publishers.append(node_id)
        for tname in sub_names:
            tid = topic_name_to_id.get(_safe_str(tname))
            if tid and tid in topic_id_map:
                topic_id_map[tid].subscribers.append(node_id)

    return nodes, topics


def _extract_components(korva: dict) -> List[Component]:
    components: List[Component] = []
    for i, raw in enumerate(_safe_list(korva.get("component_list"))):
        if not isinstance(raw, dict):
            raw = {"component": _safe_str(raw)}
        name = _safe_str(raw.get("component") or raw.get("name") or f"component_{i}").strip()
        components.append(
            Component(
                id=f"comp.{i:03d}",
                name=name,
                type="",
                role=_safe_str(raw.get("role")),
                power_notes=_safe_str(raw.get("power_notes")),
                interface=_safe_str(raw.get("interface")),
            )
        )
    return components


def _extract_power_rails(korva: dict) -> List[PowerRail]:
    rails: List[PowerRail] = []
    seen_labels: set = set()
    for assumption in _safe_list(korva.get("power_assumptions")):
        text = _safe_str(assumption)
        for v in _VOLT_RE.findall(text):
            label = f"{v}V Rail"
            if label not in seen_labels:
                seen_labels.add(label)
                rails.append(
                    PowerRail(
                        id=f"rail.{len(rails):03d}",
                        label=label,
                        voltage_hint=f"{v}V",
                    )
                )
    # If power assumptions exist but no voltages parsed, emit one generic rail.
    if not rails and _safe_list(korva.get("power_assumptions")):
        rails.append(PowerRail(id="rail.000", label="Main Power Rail", voltage_hint=""))
    return rails


def _extract_data_buses(korva: dict) -> List[DataBus]:
    buses: List[DataBus] = []
    seen: set = set()
    for s in _safe_list(korva.get("communication_buses")):
        text = _safe_str(s)
        for proto in _KNOWN_PROTOCOLS:
            if proto.lower() in text.lower() and proto not in seen:
                seen.add(proto)
                buses.append(
                    DataBus(
                        id=f"bus.{len(buses):03d}",
                        label=f"{proto} Bus",
                        protocol=proto,
                    )
                )
    return buses


def _extract_cad_features(oli: dict, artifacts: dict) -> List[CadFeature]:
    # Prefer oli.fusion360_modeling_plan; fall back to artifacts.fusion360_concept.modeling_plan.
    raw_plan = _safe_list(oli.get("fusion360_modeling_plan"))
    if not raw_plan:
        fc = _safe_dict(artifacts.get("fusion360_concept"))
        raw_plan = _safe_list(fc.get("modeling_plan"))

    features: List[CadFeature] = []
    for i, raw in enumerate(raw_plan):
        if isinstance(raw, dict):
            params = _safe_list(raw.get("parameters"))
            features.append(
                CadFeature(
                    id=f"cad.{i:03d}",
                    step=_safe_str(raw.get("step")),
                    purpose=_safe_str(raw.get("purpose")),
                    geometry=_safe_str(raw.get("geometry")),
                    parameters=[_safe_str(p) for p in params],
                )
            )
        else:
            features.append(CadFeature(id=f"cad.{i:03d}", step=_safe_str(raw)))
    return features


def _extract_physics_subsystems(isy: dict) -> List[PhysicsSubsystem]:
    subsystems: List[PhysicsSubsystem] = []
    for raw in _safe_list(isy.get("major_subsystems")):
        if not isinstance(raw, dict):
            continue
        name = _safe_str(raw.get("name") or "subsystem").strip()
        subsystems.append(
            PhysicsSubsystem(
                id=f"subsys.{_slugify(name)}",
                name=name,
                purpose=_safe_str(raw.get("purpose")),
                inputs=[_safe_str(x) for x in _safe_list(raw.get("inputs"))],
                outputs=[_safe_str(x) for x in _safe_list(raw.get("outputs"))],
                notes=[_safe_str(x) for x in _safe_list(raw.get("notes"))],
            )
        )
    return subsystems


def _extract_requirements(isy: dict) -> List[Requirement]:
    reqs: List[Requirement] = []
    for i, item in enumerate(_safe_list(isy.get("validation_items"))):
        text = _safe_str(item).strip()
        if not text:
            continue
        reqs.append(
            Requirement(
                id=f"req.{i:03d}",
                text=text,
                source="isy.validation_items",
                status="unverified",
            )
        )
    return reqs


def _extract_morphology(isy: dict) -> List[Morphology]:
    geo_items = _safe_list(isy.get("mass_and_geometry_assumptions"))
    if not geo_items:
        return []
    description = " ".join(_safe_str(g) for g in geo_items).strip()
    if not description:
        return []
    return [
        Morphology(
            id="morph.000",
            source="isy.mass_and_geometry_assumptions",
            description=description,
            body_region_ids=[],
        )
    ]


def _extract_validation_checks(validation: dict) -> List[ValidationCheck]:
    checks: List[ValidationCheck] = []
    idx = 0

    conf_scores = _safe_dict(validation.get("confidence_scores"))
    for domain, score in conf_scores.items():
        try:
            s = float(score)
        except (TypeError, ValueError):
            s = 0.0
        status: str = "PASS" if s >= 8.0 else ("WARNING" if s >= 6.0 else "FAIL")
        checks.append(
            ValidationCheck(
                id=f"check.{idx:03d}",
                name=_safe_str(domain),
                status=status,  # type: ignore[arg-type]
                source="validation_report.confidence_scores",
                notes=f"Score: {s:.2f}/10",
            )
        )
        idx += 1

    for item in _safe_list(validation.get("missing_evidence")):
        checks.append(
            ValidationCheck(
                id=f"check.{idx:03d}",
                name="Missing Evidence",
                status="FAIL",
                source="validation_report.missing_evidence",
                notes=_safe_str(item),
            )
        )
        idx += 1

    # Overall verdict as a summary check.
    verdict = _safe_str(validation.get("verdict")).strip()
    if verdict:
        score_val = validation.get("score")
        try:
            score_f = float(score_val)
            score_str = f"{score_f:.2f}/10"
        except (TypeError, ValueError):
            score_str = _safe_str(score_val)
        v_status: str = "PASS" if "PASS" in verdict.upper() else ("FAIL" if "FAIL" in verdict.upper() else "WARNING")
        checks.append(
            ValidationCheck(
                id=f"check.{idx:03d}",
                name="QaZ Overall Verdict",
                status=v_status,  # type: ignore[arg-type]
                source="validation_report.verdict",
                notes=f"{verdict} — {score_str}",
            )
        )

    return checks


def _extract_generated_files(export_manifest: dict, folder: Path) -> List[GeneratedFile]:
    files: List[GeneratedFile] = []
    raw = _safe_list(export_manifest.get("files_to_generate_next"))
    for i, path_str in enumerate(raw):
        path_str = _safe_str(path_str).strip()
        if not path_str:
            continue
        ext = Path(path_str).suffix.lower()
        files.append(
            GeneratedFile(
                id=f"file.{i:03d}",
                path=path_str,
                file_type=_EXT_TO_TYPE.get(ext, "unknown"),
                source="export_manifest",
            )
        )
    return files


def _extract_provenance(provenance_data: dict) -> List[ProvenanceRef]:
    refs: List[ProvenanceRef] = []
    for agent in _safe_list(provenance_data.get("agents")):
        if not isinstance(agent, dict):
            continue
        agent_id = _safe_str(agent.get("agent_id") or "unknown")
        refs.append(
            ProvenanceRef(
                id=f"prov.{agent_id}",
                agent_id=agent_id,
                agent_name=_safe_str(agent.get("agent_name") or agent_id),
                status=_safe_str(agent.get("status") or "unknown"),
                source="provenance_record.json",
                evidence_type=_safe_str(agent.get("evidence_type") or "llm_generated"),
                human_review_required=bool(agent.get("human_review_required", True)),
            )
        )
    return refs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_graph(folder: Path) -> MissionKnowledgeGraph:
    """
    Build a MissionKnowledgeGraph from a harness-produced mission folder.

    Reads:
      mission_result.json  (required; falls back to mission.json)
      validation_report.json   (optional)
      next_artifacts.json      (optional)
      provenance_record.json   (optional)

    Missing or malformed files emit ConsistencyWarnings instead of raising.
    """
    load_warnings: List[str] = []

    # --- Load files -----------------------------------------------------------
    result_data, err = _load_json(folder / "mission_result.json")
    if err:
        result_data2, err2 = _load_json(folder / "mission.json")
        if not err2:
            result_data = result_data2
        else:
            load_warnings.append(f"mission_result.json: {err}")
    result: dict = _safe_dict(result_data)

    validation_raw, verr = _load_json(folder / "validation_report.json")
    validation: dict = _safe_dict(validation_raw)
    if verr:
        load_warnings.append(f"validation_report.json: {verr}")

    next_arts_raw, _ = _load_json(folder / "next_artifacts.json")
    next_artifacts: List[str] = _safe_list(next_arts_raw)

    prov_raw, _ = _load_json(folder / "provenance_record.json")
    provenance_data: dict = _safe_dict(prov_raw)

    # --- Extract sub-structures -----------------------------------------------
    sao: dict = _safe_dict(result.get("structured_agent_outputs"))
    sky: dict = _safe_dict(sao.get("sky"))
    isy: dict = _safe_dict(sao.get("isy"))
    oli: dict = _safe_dict(sao.get("oli"))
    korva: dict = _safe_dict(sao.get("korva"))
    artifacts: dict = _safe_dict(result.get("artifacts"))
    export_manifest: dict = _safe_dict(result.get("export_manifest"))

    mission_id: Optional[str] = result.get("mission_id") or result.get("result_id")
    mission_text: str = _safe_str(result.get("mission") or result.get("mission_text"))
    platform: str = _extract_platform(mission_text)

    ros2_nodes, ros2_topics = _extract_ros2(sky)
    components = _extract_components(korva)
    power_rails = _extract_power_rails(korva)
    data_buses = _extract_data_buses(korva)
    cad_features = _extract_cad_features(oli, artifacts)
    physics_subsystems = _extract_physics_subsystems(isy)
    requirements = _extract_requirements(isy)
    morphology = _extract_morphology(isy)
    validation_checks = _extract_validation_checks(validation)
    generated_files = _extract_generated_files(export_manifest, folder)
    provenance = _extract_provenance(provenance_data)

    # --- Build draft graph (no consistency_warnings yet) ----------------------
    from backend.app.mission_graph.validators import check_graph

    graph = MissionKnowledgeGraph(
        graph_id=uuid4().hex[:12],
        generated_at=datetime.now(timezone.utc).isoformat(),
        mission_id=mission_id,
        mission_text=mission_text,
        platform=platform,
        requirements=requirements,
        morphology=morphology,
        body_regions=[],
        ros2_nodes=ros2_nodes,
        ros2_topics=ros2_topics,
        components=components,
        power_rails=power_rails,
        data_buses=data_buses,
        cad_features=cad_features,
        physics_subsystems=physics_subsystems,
        validation_checks=validation_checks,
        generated_files=generated_files,
        provenance=provenance,
        next_artifacts=[_safe_str(a) for a in next_artifacts if a],
        consistency_warnings=[],
    )

    # --- Enrich relationships -------------------------------------------------
    from backend.app.mission_graph.enrichment import enrich_graph
    enrich_graph(graph)

    # --- Run consistency checks, prepend file-load warnings -------------------
    structural_warnings = check_graph(graph)

    # Offset structural warning IDs to avoid collision with load warnings.
    load_cw = [
        ConsistencyWarning(
            id=f"warn.load.{i:03d}",
            code="LOAD_WARNING",
            severity="info",
            message=msg,
            related_ids=[],
        )
        for i, msg in enumerate(load_warnings)
    ]

    graph.consistency_warnings = load_cw + structural_warnings
    return graph
