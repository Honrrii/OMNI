import { useState } from "react";

function placeholderText(asset) {
  if (!asset) return "No asset selected.";
  const kind = asset.kind ?? "";

  if (asset.execution_blocked) {
    return "Execution-capable or external-tool asset. Preview is blocked.";
  }
  if (kind === "glb" || kind === "gltf") {
    if (asset.browser_preview_ready) {
      return "Browser-compatible asset detected. Rendering support will be added in a later phase.";
    }
    return "Browser-compatible asset detected. Rendering support will be added in a later phase.";
  }
  if (kind === "stl" || kind === "obj") {
    return "Mesh asset detected. STL viewer support pending.";
  }
  if (kind === "urdf" || kind === "xacro") {
    return "Robot description detected. URDF parser/viewer not implemented yet.";
  }
  if (kind === "step" || kind === "iges") {
    return "Engineering CAD file detected. External CAD tooling required.";
  }
  if (kind === "rviz" || kind === "ros2_launch") {
    return "Execution-capable or external-tool asset. Preview is blocked.";
  }
  if (kind === "fusion_script" || kind === "cadquery_script") {
    return "Execution-capable or external-tool asset. Preview is blocked.";
  }
  return "Asset metadata only. No rendering available in this phase.";
}

function ViewerChip({ label, variant }) {
  return (
    <span className={`vb-preview-asset-chip vb-preview-asset-chip-${variant}`}>
      {label}
    </span>
  );
}

function assetChips(asset) {
  const chips = [];
  if (asset.browser_preview_ready)
    chips.push(<ViewerChip key="ready"    label="Browser asset available"    variant="ready"       />);
  if (asset.browser_preview_candidate && !asset.browser_preview_ready)
    chips.push(<ViewerChip key="cand"     label="Preview candidate"          variant="candidate"   />);
  if (asset.engineering_only)
    chips.push(<ViewerChip key="eng"      label="Engineering-only"           variant="engineering" />);
  if (asset.execution_blocked)
    chips.push(<ViewerChip key="blocked"  label="Execution blocked"          variant="blocked"     />);
  if (asset.requires_conversion)
    chips.push(<ViewerChip key="conv"     label="Conversion/parser required" variant="conversion"  />);
  if (asset.requires_external_tool)
    chips.push(<ViewerChip key="ext"      label="External tool required"     variant="external"    />);
  return chips;
}

function defaultIndex(assets) {
  let idx = assets.findIndex((a) => a.browser_preview_ready);
  if (idx !== -1) return idx;
  idx = assets.findIndex((a) => a.browser_preview_candidate);
  if (idx !== -1) return idx;
  return 0;
}

function shortLabel(asset) {
  if (!asset?.path) return "asset";
  const parts = asset.path.replace(/\\/g, "/").split("/");
  return parts[parts.length - 1] || asset.path;
}

export default function VisualBayViewerShell({ previewAssets }) {
  const assets = previewAssets ?? [];
  const [selected, setSelected] = useState(() => defaultIndex(assets));

  if (assets.length === 0) return null;

  const safeIdx  = Math.min(selected, assets.length - 1);
  const asset    = assets[safeIdx];
  const chips    = assetChips(asset);
  const phText   = placeholderText(asset);

  const stageVariant = asset.execution_blocked ? "blocked"
    : asset.browser_preview_ready              ? "ready"
    : asset.engineering_only                   ? "engineering"
    : "default";

  return (
    <div className="visual-bay-section">
      <span className="vb-section-label">Static Viewer Shell</span>
      <div className="vb-section-body">
        <div className="visual-bay-viewer-shell">

          {/* ── Asset selector ── */}
          <div className="vb-viewer-asset-selector">
            {assets.map((a, i) => (
              <button
                key={i}
                type="button"
                className={`vb-viewer-asset-button${i === safeIdx ? " vb-viewer-asset-button-active" : ""}${a.execution_blocked ? " vb-viewer-asset-button-blocked" : a.browser_preview_ready ? " vb-viewer-asset-button-ready" : ""}`}
                onClick={() => setSelected(i)}
                aria-pressed={i === safeIdx}
              >
                {shortLabel(a)}
              </button>
            ))}
          </div>

          {/* ── Selected asset metadata ── */}
          <div className="vb-viewer-asset-meta">
            <div className="vb-preview-asset-path">{asset.path}</div>
            <div className="vb-preview-asset-kind">{asset.kind}</div>
            {chips.length > 0 && (
              <div className="vb-preview-asset-chips" style={{ marginTop: "6px" }}>
                {chips}
              </div>
            )}
            {asset.notes && asset.notes.length > 0 && (
              <ul className="vb-preview-asset-notes">
                {asset.notes.map((n, i) => <li key={i}>{n}</li>)}
              </ul>
            )}
          </div>

          {/* ── Viewer placeholder stage ── */}
          <div className={`vb-viewer-shell-stage vb-viewer-shell-stage-${stageVariant}`}>
            <p className="vb-viewer-placeholder">{phText}</p>
            <p className="vb-viewer-warning">
              Viewer shell only — rendering not enabled in this phase.
              <br />
              No files fetched. No scripts executed. No simulation launched.
            </p>
          </div>

        </div>
      </div>
    </div>
  );
}
