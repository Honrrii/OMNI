"""
Mission Knowledge Graph v0.1 — graph relationship enrichment.

Deterministic, structural passes that add cross-references to a draft graph.
No LLM calls. No file I/O. Modifies graph in-place; returns same object.
"""
from __future__ import annotations

import re
from typing import Dict

from backend.app.mission_graph.schemas import BodyRegion, MissionKnowledgeGraph


_VOLT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[Vv](?:olt)?")



def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower().strip()).strip("-") or "unknown"


def _normalize_platform(graph: MissionKnowledgeGraph) -> None:
    from backend.app.platform_intent import resolve_platform_slug
    text = graph.platform or graph.mission_text or ""
    slug = resolve_platform_slug(text)
    if slug:
        graph.platform_normalized = slug
    elif graph.platform:
        graph.platform_normalized = _slugify(graph.platform)


def _link_components_to_power_rails(graph: MissionKnowledgeGraph) -> None:
    if not graph.power_rails:
        return
    rail_map: Dict[str, str] = {}
    for rail in graph.power_rails:
        hint = rail.voltage_hint.strip()
        if hint:
            v = hint.rstrip("Vv").strip()
            if v:
                rail_map[v] = rail.id
    for comp in graph.components:
        if comp.power_rail_id:
            continue
        for v in _VOLT_RE.findall(comp.power_notes):
            if v in rail_map:
                comp.power_rail_id = rail_map[v]
                break


def _link_components_to_data_buses(graph: MissionKnowledgeGraph) -> None:
    if not graph.data_buses:
        return
    for comp in graph.components:
        if comp.data_bus_id:
            continue
        iface_lower = comp.interface.lower()
        for bus in graph.data_buses:
            if bus.protocol and bus.protocol.lower() in iface_lower:
                comp.data_bus_id = bus.id
                break


def _link_nodes_to_components(graph: MissionKnowledgeGraph) -> None:
    if not graph.components or not graph.ros2_nodes:
        return
    for node in graph.ros2_nodes:
        node_text = f"{node.name} {node.purpose}".lower()
        for comp in graph.components:
            if comp.id in node.component_ids:
                continue
            comp_text = f"{comp.name} {comp.role}".lower()
            words = [w for w in re.split(r"\W+", comp_text) if len(w) >= 4]
            if any(w in node_text for w in words):
                node.component_ids.append(comp.id)


def _infer_body_regions_from_morphology(graph: MissionKnowledgeGraph) -> None:
    if graph.body_regions or not graph.morphology:
        return
    for i, morph in enumerate(graph.morphology):
        if morph.body_region_ids:
            continue
        region_id = f"region.{i:03d}"
        graph.body_regions.append(
            BodyRegion(
                id=region_id,
                name=f"Region {i}",
                description=(morph.description[:80] if morph.description else ""),
            )
        )
        morph.body_region_ids.append(region_id)


def _link_cad_features_to_body_regions(graph: MissionKnowledgeGraph) -> None:
    if not graph.body_regions or not graph.cad_features:
        return
    region_ids = [r.id for r in graph.body_regions]
    for feat in graph.cad_features:
        if feat.body_region_id:
            continue
        if region_ids:
            feat.body_region_id = region_ids[0]


def _link_components_to_body_regions(graph: MissionKnowledgeGraph) -> None:
    if not graph.body_regions or not graph.components:
        return
    region_ids = [r.id for r in graph.body_regions]
    for comp in graph.components:
        if comp.body_region_id:
            continue
        if region_ids:
            comp.body_region_id = region_ids[0]


def enrich_graph(graph: MissionKnowledgeGraph) -> MissionKnowledgeGraph:
    """
    Run all relationship-enrichment passes on a draft graph.
    Modifies graph in-place; returns the same object.
    """
    _normalize_platform(graph)
    _link_components_to_power_rails(graph)
    _link_components_to_data_buses(graph)
    _link_nodes_to_components(graph)
    _infer_body_regions_from_morphology(graph)
    _link_cad_features_to_body_regions(graph)
    _link_components_to_body_regions(graph)
    return graph
