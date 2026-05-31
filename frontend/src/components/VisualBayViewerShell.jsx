import { lazy, Suspense, useState } from "react";

const VisualBayGlbViewer = lazy(() => import("./VisualBayGlbViewer.jsx"));

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

function assetChips(asset, canRenderGlb) {
  const chips = [];

  const isPlaceholder = asset.path?.includes("generated_visual_bay/preview_scene.gltf");

  if (canRenderGlb) {
    chips.push(<ViewerChip key="active" label="Browser visualization active" variant="active"      />);
  } else if (asset.browser_preview_ready) {
    chips.push(<ViewerChip key="ready"  label="Browser asset available"      variant="ready"       />);
  }
  if (isPlaceholder) {
    chips.push(<ViewerChip key="placeholder" label="Placeholder geometry" variant="placeholder" />);
    chips.push(<ViewerChip key="notcad"      label="Not CAD-accurate"     variant="placeholder" />);
  }
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

function UrlChip({ label, variant }) {
  return (
    <span className={`vb-viewer-url-chip vb-viewer-url-chip-${variant}`}>
      {label}
    </span>
  );
}

function AssetUrlBlock({ asset, canRenderGlb }) {
  const hasUrl = !!asset?.asset_url;

  if (hasUrl) {
    return (
      <div className="vb-viewer-asset-url">
        <div className="vb-viewer-url-chips">
          <UrlChip label="Controlled URL"    variant="controlled" />
          <UrlChip label="Read-only serving" variant="readonly"   />
          {canRenderGlb
            ? <UrlChip label="Browser visualization active" variant="active"  />
            : <UrlChip label="Rendering pending"             variant="pending" />
          }
        </div>
        <div className="vb-viewer-url-box">{asset.asset_url}</div>
        <p className="vb-viewer-url-note">
          {canRenderGlb
            ? "Browser visualization active. Read-only serving — no files modified. No engineering validation implied. No simulation launched. No scripts executed."
            : "Serving is read-only; rendering not enabled for this asset type."
          }
        </p>
      </div>
    );
  }

  return (
    <div className="vb-viewer-asset-url">
      <div className="vb-viewer-url-chips">
        <UrlChip label="No URL exposed" variant="none" />
      </div>
      {asset?.execution_blocked && (
        <p className="vb-viewer-url-note vb-viewer-url-note-blocked">
          Asset is blocked from serving.
        </p>
      )}
      {asset?.engineering_only && !asset?.execution_blocked && (
        <p className="vb-viewer-url-note">
          External engineering tool may be required.
        </p>
      )}
    </div>
  );
}

export default function VisualBayViewerShell({ previewAssets }) {
  const assets = previewAssets ?? [];
  const [selected, setSelected] = useState(() => defaultIndex(assets));

  if (assets.length === 0) return null;

  const safeIdx  = Math.min(selected, assets.length - 1);
  const asset    = assets[safeIdx];
  const phText   = placeholderText(asset);

  const stageVariant = asset.execution_blocked ? "blocked"
    : asset.browser_preview_ready              ? "ready"
    : asset.engineering_only                   ? "engineering"
    : "default";

  // Hard gate: ALL conditions must pass before the GLB viewer activates.
  const canRenderGlb = (
    (asset.kind === "glb" || asset.kind === "gltf") &&
    !!asset.asset_url &&
    asset.browser_preview_ready === true &&
    asset.execution_blocked !== true
  );

  const chips = assetChips(asset, canRenderGlb);

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
            <AssetUrlBlock asset={asset} canRenderGlb={canRenderGlb} />
          </div>

          {/* ── Viewer stage: GLB renderer or safe placeholder ── */}
          {canRenderGlb ? (
            <Suspense fallback={
              <div className="vb-glb-viewer-fallback">
                <p>Loading browser visualization shell…</p>
                <p className="vb-glb-viewer-fallback-note">
                  No engineering validation implied.
                  No simulation launched.
                  No scripts executed.
                </p>
              </div>
            }>
              <VisualBayGlbViewer asset={asset} />
            </Suspense>
          ) : (
            <div className={`vb-viewer-shell-stage vb-viewer-shell-stage-${stageVariant}`}>
              <p className="vb-viewer-placeholder">{phText}</p>
              <p className="vb-viewer-warning">
                Viewer shell only — rendering not enabled for this asset type.
                <br />
                No files fetched. No scripts executed. No simulation launched.
              </p>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
