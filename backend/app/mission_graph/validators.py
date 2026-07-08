"""
Mission Knowledge Graph v0.1 — consistency validators.

All checks are deterministic and purely structural.
No LLM calls. No file I/O.
Missing data emits warnings, not crashes.
"""
from __future__ import annotations

from typing import List

from backend.app.mission_graph.schemas import (
    ConsistencyWarning,
    MissionKnowledgeGraph,
)


def check_graph(graph: MissionKnowledgeGraph) -> List[ConsistencyWarning]:
    """
    Run all consistency checks on a built graph.
    Returns a list of ConsistencyWarning objects.
    Ids are assigned sequentially: warn.000, warn.001, …
    """
    warnings: List[ConsistencyWarning] = []

    def _add(code: str, message: str, severity: str = "warning", related_ids: list = []) -> None:
        warnings.append(
            ConsistencyWarning(
                id=f"warn.{len(warnings):03d}",
                code=code,
                severity=severity,  # type: ignore[arg-type]
                message=message,
                related_ids=list(related_ids),
            )
        )

    # Pre-build lookup sets for O(1) checks.
    topic_ids = {t.id for t in graph.ros2_topics}
    power_rail_ids = {r.id for r in graph.power_rails}
    body_region_ids = {r.id for r in graph.body_regions}

    # 1. Orphan topic: topic has no publishers AND no subscribers.
    for topic in graph.ros2_topics:
        if not topic.publishers and not topic.subscribers:
            _add(
                code="ORPHAN_TOPIC",
                message=(
                    f"ROS2 topic '{topic.name}' has no publishers or subscribers "
                    "in the node graph."
                ),
                severity="warning",
                related_ids=[topic.id],
            )

    # 2. Component ros2_topic_id references a non-existent topic.
    for comp in graph.components:
        if comp.ros2_topic_id and comp.ros2_topic_id not in topic_ids:
            _add(
                code="MISSING_ROS2_TOPIC_REF",
                message=(
                    f"Component '{comp.name}' references ros2_topic_id "
                    f"'{comp.ros2_topic_id}' which does not exist in ros2_topics."
                ),
                severity="warning",
                related_ids=[comp.id],
            )

    # 3. Powered component without a power_rail_id (only when power rails are defined).
    if graph.power_rails:
        for comp in graph.components:
            if comp.power_notes and not comp.power_rail_id:
                _add(
                    code="UNPOWERED_COMPONENT",
                    message=(
                        f"Component '{comp.name}' has power notes but no power_rail_id "
                        "assigned. Consider linking it to a power rail."
                    ),
                    severity="info",
                    related_ids=[comp.id],
                )

    # 4. CAD feature body_region_id references a non-existent region.
    for feat in graph.cad_features:
        if feat.body_region_id and feat.body_region_id not in body_region_ids:
            _add(
                code="MISSING_BODY_REGION",
                message=(
                    f"CadFeature '{feat.step or feat.id}' references body_region_id "
                    f"'{feat.body_region_id}' which does not exist in body_regions."
                ),
                severity="warning",
                related_ids=[feat.id],
            )

    # 5. FAIL validation checks surface as graph-level errors.
    for check in graph.validation_checks:
        if check.status == "FAIL":
            _add(
                code="VALIDATION_FAIL",
                message=f"Validation check '{check.name}' is FAIL. {check.notes}".strip(),
                severity="error",
                related_ids=[check.id],
            )

    # 6. Missing requirements: no structured requirements were extracted.
    if not graph.requirements:
        _add(
            code="MISSING_REQUIREMENTS",
            message=(
                "No structured requirements were extracted from this mission. "
                "Add explicit requirements for traceability."
            ),
            severity="info",
        )

    # 7. Missing morphology: body-region cross-references are unavailable.
    if not graph.morphology:
        _add(
            code="MISSING_MORPHOLOGY",
            message=(
                "No morphology was extracted. Body-region cross-references are "
                "unavailable for components and CAD features."
            ),
            severity="info",
        )

    return warnings
