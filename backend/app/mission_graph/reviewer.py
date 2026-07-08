"""
Mission Knowledge Graph v0.1 — deterministic graph reviewer.

Consumes a MissionKnowledgeGraph and returns a MissionGraphReview
summarising relationship coverage, warnings, and recommendations.
No LLM calls. No file I/O. Fully deterministic.
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from backend.app.mission_graph.schemas import ConsistencyWarning, MissionKnowledgeGraph


class ComponentCoverage(BaseModel):
    total: int = 0
    with_power_rail_id: int = 0
    with_data_bus_id: int = 0
    with_body_region_id: int = 0


class Ros2Coverage(BaseModel):
    total_nodes: int = 0
    nodes_with_component_ids: int = 0


class MorphologyCadCoverage(BaseModel):
    total_morphology: int = 0
    total_body_regions: int = 0
    total_cad_features: int = 0
    cad_features_with_body_region_id: int = 0


class MissionGraphReviewIssue(BaseModel):
    code: str
    severity: str
    category: str
    message: str
    related_ids: List[str] = Field(default_factory=list)


class MissionGraphReview(BaseModel):
    graph_id: str
    platform: str = ""
    platform_normalized: str = ""
    component_coverage: ComponentCoverage = Field(default_factory=ComponentCoverage)
    ros2_coverage: Ros2Coverage = Field(default_factory=Ros2Coverage)
    morphology_cad_coverage: MorphologyCadCoverage = Field(default_factory=MorphologyCadCoverage)
    issues: List[MissionGraphReviewIssue] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)  # derived from issues.message; kept for backwards compatibility
    recommendations: List[str] = Field(default_factory=list)
    consistency_warnings: List[ConsistencyWarning] = Field(default_factory=list)


def review_graph(graph: MissionKnowledgeGraph) -> MissionGraphReview:
    """Return a deterministic review of graph relationship coverage."""
    issues: List[MissionGraphReviewIssue] = []
    recommendations: List[str] = []

    # --- Component coverage ---------------------------------------------------
    comp_total = len(graph.components)
    comp_with_power = sum(1 for c in graph.components if c.power_rail_id)
    comp_with_bus = sum(1 for c in graph.components if c.data_bus_id)
    comp_with_region = sum(1 for c in graph.components if c.body_region_id)

    for comp in graph.components:
        if not comp.power_rail_id:
            issues.append(MissionGraphReviewIssue(
                code="COMP_MISSING_POWER_RAIL",
                severity="warning",
                category="component",
                message=f"component '{comp.name}' ({comp.id}) missing power_rail_id",
                related_ids=[comp.id],
            ))
        if not comp.data_bus_id:
            issues.append(MissionGraphReviewIssue(
                code="COMP_MISSING_DATA_BUS",
                severity="warning",
                category="component",
                message=f"component '{comp.name}' ({comp.id}) missing data_bus_id",
                related_ids=[comp.id],
            ))
        if not comp.body_region_id:
            issues.append(MissionGraphReviewIssue(
                code="COMP_MISSING_BODY_REGION",
                severity="warning",
                category="component",
                message=f"component '{comp.name}' ({comp.id}) missing body_region_id",
                related_ids=[comp.id],
            ))

    # --- ROS2 coverage --------------------------------------------------------
    node_total = len(graph.ros2_nodes)
    nodes_with_comp = sum(1 for n in graph.ros2_nodes if n.component_ids)

    for node in graph.ros2_nodes:
        if not node.component_ids:
            issues.append(MissionGraphReviewIssue(
                code="NODE_MISSING_COMPONENT_LINK",
                severity="warning",
                category="ros2",
                message=f"ros2_node '{node.name}' ({node.id}) missing component_ids",
                related_ids=[node.id],
            ))

    # --- Morphology / CAD coverage --------------------------------------------
    morph_total = len(graph.morphology)
    region_total = len(graph.body_regions)
    cad_total = len(graph.cad_features)
    cad_with_region = sum(1 for f in graph.cad_features if f.body_region_id)

    for feat in graph.cad_features:
        if not feat.body_region_id:
            issues.append(MissionGraphReviewIssue(
                code="CAD_MISSING_BODY_REGION",
                severity="warning",
                category="cad",
                message=f"cad_feature '{feat.id}' missing body_region_id",
                related_ids=[feat.id],
            ))

    # warnings is derived from issues to stay in sync (backwards compatibility)
    warnings = [i.message for i in issues]

    # --- Recommendations ------------------------------------------------------
    missing_power = comp_total - comp_with_power
    missing_bus = comp_total - comp_with_bus
    missing_region_comps = comp_total - comp_with_region
    missing_node_comp = node_total - nodes_with_comp
    missing_cad_region = cad_total - cad_with_region

    if missing_power:
        recommendations.append(
            f"Add power_notes with voltage to {missing_power} component(s) so power rail links can be resolved."
        )
    if missing_bus:
        recommendations.append(
            f"Add interface/protocol to {missing_bus} component(s) so data bus links can be resolved."
        )
    if missing_region_comps:
        recommendations.append(
            f"Add body_region entries so {missing_region_comps} component(s) can be spatially located."
        )
    if missing_node_comp:
        recommendations.append(
            f"Enrich {missing_node_comp} ROS2 node(s) with component keyword overlap to resolve component links."
        )
    if missing_cad_region:
        recommendations.append(
            f"Assign body regions to {missing_cad_region} CAD feature(s) for spatial traceability."
        )
    if graph.platform and not graph.platform_normalized:
        recommendations.append(
            f"Platform '{graph.platform}' could not be normalized; add an alias in enrichment._PLATFORM_ALIASES."
        )
    elif not graph.platform and not graph.platform_normalized:
        recommendations.append(
            "No platform detected; set mission_text or platform for full enrichment."
        )

    return MissionGraphReview(
        graph_id=graph.graph_id,
        platform=graph.platform,
        platform_normalized=graph.platform_normalized,
        component_coverage=ComponentCoverage(
            total=comp_total,
            with_power_rail_id=comp_with_power,
            with_data_bus_id=comp_with_bus,
            with_body_region_id=comp_with_region,
        ),
        ros2_coverage=Ros2Coverage(
            total_nodes=node_total,
            nodes_with_component_ids=nodes_with_comp,
        ),
        morphology_cad_coverage=MorphologyCadCoverage(
            total_morphology=morph_total,
            total_body_regions=region_total,
            total_cad_features=cad_total,
            cad_features_with_body_region_id=cad_with_region,
        ),
        issues=issues,
        warnings=warnings,
        recommendations=recommendations,
        consistency_warnings=list(graph.consistency_warnings),
    )
