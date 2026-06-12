# `findings_projection` contract

Status: stable, additive (OMNI Phase 10 Stage 4)

## Overview

`findings_projection` is an **additive**, read-only, normalized view of the
finding-like shapes already present in three existing report files. It gives
consumers a single, predictable item shape across reports that were authored
with different internal models, *without* changing those reports.

The projection is attached as a top-level `findings_projection` key on each of
these report JSON documents:

| Report file | Envelope `schema` | Envelope `source` |
| --- | --- | --- |
| `mission_graph_review.json` | `omni.mission_graph.findings_projection.v1` | `mission_graph_review` |
| `generated_kicad/kicad_knowledge_gate_report.json` | `omni.engineering.kicad_knowledge_gate.findings_projection.v1` | `kicad_knowledge_gate_report` |
| `artifacts/morphology_gate_report.json` | `omni.engineering.morphology_gate.findings_projection.v1` | `morphology_gate_report` |

The projection **never** replaces the report's existing fields. Those legacy
fields (e.g. `issues`, `consistency_warnings`, `summary`, validator/reviewer
model output) remain authoritative and unchanged. `findings_projection` is a
convenience normalization layered *on top of* them.

## Envelope

Each `findings_projection` value is an object with exactly these keys:

| Key | Type | Meaning |
| --- | --- | --- |
| `schema` | string | Versioned identifier for the projection shape. See known values below. |
| `source` | string | Identifies the report the projection was derived from. See known values below. |
| `origin_fields` | array of string | The report fields that were projected into `items`, in projection order. |
| `count` | integer | Number of projected findings. **Always equals `len(items)`.** |
| `items` | array of object | The normalized findings. See item shape below. |

### Known envelope `schema` strings

- `omni.mission_graph.findings_projection.v1`
- `omni.engineering.kicad_knowledge_gate.findings_projection.v1`
- `omni.engineering.morphology_gate.findings_projection.v1`

### Known envelope `source` strings

- `mission_graph_review`
- `kicad_knowledge_gate_report`
- `morphology_gate_report`

### `origin_fields` per report

- `mission_graph_review.json` → `["issues", "consistency_warnings"]`
- `generated_kicad/kicad_knowledge_gate_report.json` → `["issues"]`
- `artifacts/morphology_gate_report.json` → `["issues"]`

For the mission graph review, `issues` are projected first (in order), followed
by `consistency_warnings` (in order).

## Item shape

Every item in `items` has the same key set, regardless of which report it came
from:

| Key | Type | Notes |
| --- | --- | --- |
| `id` | string \| null | Source-provided id when one exists (e.g. consistency warnings), otherwise `null`. |
| `code` | string \| null | Source rule/issue code (mission `code`, engineering `rule_id`). May be `null`. |
| `source` | string | Per-item origin. See known item `source` strings below. |
| `category` | string | Coarse grouping (e.g. `consistency`, `engineering`, or the issue's own category). |
| `severity` | string | Lowercased. Known values: `info`, `warning`, `error`, `blocker`. Unknown non-empty values are preserved lowercased; empty/non-string becomes `warning`. |
| `status` | string | Currently always `open`. |
| `message` | string \| null | Human-readable description from the source finding. |
| `recommendation` | string \| null | Reserved; currently `null`. |
| `related_ids` | array of string | Related node/finding ids; may be empty. |
| `file` | string \| null | Associated file path when the source has one (engineering gates), else `null`. |
| `evidence_ids` | array of string | Reserved; currently `[]`. |
| `requires_human_review` | boolean | Currently always `false`. |
| `metadata` | object | Source-specific, **extensible** context. See note below. |

### Known item `source` strings

- `mission_graph_review`
- `mission_graph_consistency`
- `kicad_knowledge_gate`
- `morphology_gate`

### `metadata`

`metadata` is intentionally **extensible and source-specific**. It always
includes an `origin` key naming the internal shape it was projected from
(e.g. `MissionGraphReviewIssue`, `ConsistencyWarning`, `KiCadGateIssue`,
`MorphologyGateIssue`). Engineering projections additionally include a
`validator` key and may fold in small scalar report context (e.g. `kicad_dir`,
`export_dir`, `morphology_id`, `project_family`, `report_status`).

Consumers **must tolerate unknown `metadata` keys** — new keys may be added
without a schema bump. Do not assume a closed `metadata` key set.

## Consumer rules

- Use the envelope `schema` and `source` to decide how to interpret a
  projection. Do not infer meaning from file location alone.
- Treat `count` as a convenience; if it ever disagrees with `len(items)`,
  `items` is the source of truth, but by contract they are equal.
- `findings_projection` is **additive**. Legacy report fields remain
  authoritative; the raw validator/reviewer models are unchanged.
- There is **no** top-level `findings` field anywhere. The only key is
  `findings_projection`, nested inside each report.
- The KiCad projection exists **only when a KiCad gate report is generated**.
  If KiCad generation/validation was skipped, no
  `kicad_knowledge_gate_report.json` (and thus no projection) is produced.
- Tolerate unknown `metadata` keys and unknown `severity` strings.

## Examples

### `mission_graph_review.json` (truncated)

```json
{
  "issues": [ "... unchanged authoritative reviewer output ..." ],
  "consistency_warnings": [ "... unchanged ..." ],
  "findings_projection": {
    "schema": "omni.mission_graph.findings_projection.v1",
    "source": "mission_graph_review",
    "origin_fields": ["issues", "consistency_warnings"],
    "count": 2,
    "items": [
      {
        "id": null,
        "code": "MGR-ORPHAN-NODE",
        "source": "mission_graph_review",
        "category": "structure",
        "severity": "warning",
        "status": "open",
        "message": "Node 'sensor_pkg' is not referenced by any edge.",
        "recommendation": null,
        "related_ids": ["sensor_pkg"],
        "file": null,
        "evidence_ids": [],
        "requires_human_review": false,
        "metadata": {"origin": "MissionGraphReviewIssue"}
      },
      {
        "id": "cw-0007",
        "code": "CONSISTENCY_MASS_MISMATCH",
        "source": "mission_graph_consistency",
        "category": "consistency",
        "severity": "error",
        "status": "open",
        "message": "Declared mass disagrees with summed component mass.",
        "recommendation": null,
        "related_ids": ["chassis", "battery"],
        "file": null,
        "evidence_ids": [],
        "requires_human_review": false,
        "metadata": {"origin": "ConsistencyWarning"}
      }
    ]
  }
}
```

### `generated_kicad/kicad_knowledge_gate_report.json` (truncated)

```json
{
  "validator": "kicad_knowledge_gate_validator",
  "status": "completed",
  "summary": { "blockers": 1, "warnings": 0, "info": 0, "total_issues": 1 },
  "issues": [ "... unchanged authoritative validator output ..." ],
  "findings_projection": {
    "schema": "omni.engineering.kicad_knowledge_gate.findings_projection.v1",
    "source": "kicad_knowledge_gate_report",
    "origin_fields": ["issues"],
    "count": 1,
    "items": [
      {
        "id": null,
        "code": "KICAD-NO-POWER-NET",
        "source": "kicad_knowledge_gate",
        "category": "engineering",
        "severity": "blocker",
        "status": "open",
        "message": "No power net found in the generated schematic.",
        "recommendation": null,
        "related_ids": [],
        "file": "generated_kicad/project.kicad_sch",
        "evidence_ids": [],
        "requires_human_review": false,
        "metadata": {
          "origin": "KiCadGateIssue",
          "validator": "kicad_knowledge_gate_validator",
          "kicad_dir": "generated_kicad",
          "report_status": "completed"
        }
      }
    ]
  }
}
```

### `artifacts/morphology_gate_report.json` (truncated)

```json
{
  "validator": "morphology_gate_validator",
  "status": "completed",
  "summary": { "blockers": 0, "warnings": 1, "info": 0, "total_issues": 1 },
  "issues": [ "... unchanged authoritative validator output ..." ],
  "findings_projection": {
    "schema": "omni.engineering.morphology_gate.findings_projection.v1",
    "source": "morphology_gate_report",
    "origin_fields": ["issues"],
    "count": 1,
    "items": [
      {
        "id": null,
        "code": "MORPH-DOF-RANGE",
        "source": "morphology_gate",
        "category": "engineering",
        "severity": "warning",
        "status": "open",
        "message": "Joint 'elbow' range exceeds the recommended envelope.",
        "recommendation": null,
        "related_ids": [],
        "file": null,
        "evidence_ids": [],
        "requires_human_review": false,
        "metadata": {
          "origin": "MorphologyGateIssue",
          "validator": "morphology_gate_validator",
          "export_dir": "exports/mission-1234",
          "morphology_id": "morph-abc",
          "project_family": "quadruped",
          "report_status": "completed"
        }
      }
    ]
  }
}
```

> JSON examples are illustrative and truncated; the surrounding legacy fields
> (`issues`, `consistency_warnings`, `summary`, etc.) are shown abbreviated and
> remain exactly as the validator/reviewer produced them.

## Non-goals

`findings_projection` is deliberately **not**:

- **A global finding model.** Each report carries its own projection; there is
  no single consolidated/global findings document or shared finding store.
- **A frontend rendering contract.** It does not define how findings are
  displayed; it is a data normalization, not a UI schema.
- **A replacement for validator/reviewer reports.** The raw validator and
  reviewer outputs remain authoritative and unchanged; the projection is a
  derived convenience view.
- **An artifact registry.** It does not track, index, or manage artifacts; it
  only mirrors finding-like shapes from the report it is attached to.
