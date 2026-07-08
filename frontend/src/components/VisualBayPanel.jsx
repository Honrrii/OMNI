import VisualBayViewerShell from "./VisualBayViewerShell.jsx";

function getVisualBayData(exportResult, missionResult) {
  // Compact summary — preferred source
  const summary =
    exportResult?.export?.visual_bay ||
    exportResult?.visual_bay ||
    null;

  // Full manifest
  const manifest =
    exportResult?.export?.artifacts?.visual_bay_manifest ||
    exportResult?.artifacts?.visual_bay_manifest ||
    missionResult?.artifacts?.visual_bay_manifest ||
    null;

  return { summary, manifest };
}

const VB_CHIP_DS_MAP = {
  info:      "info",
  blocked:   "danger",
  ready:     "success",
  warn:      "warning",
  candidate: "muted",
};

function VbChip({ label, variant }) {
  const dsVariant = VB_CHIP_DS_MAP[variant] || "muted";
  return (
    <span className={`visual-bay-chip visual-bay-chip-${variant} omni-ds-chip omni-ds-chip-${dsVariant}`}>
      {label}
    </span>
  );
}

function VbSection({ label, children }) {
  return (
    <div className="visual-bay-section">
      <span className="vb-section-label">{label}</span>
      <div className="vb-section-body">{children}</div>
    </div>
  );
}

function VbBlockedList({ items }) {
  if (!items || items.length === 0) return null;
  return (
    <ul className="visual-bay-blocked-list">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}

function VbNoteList({ items, cls }) {
  if (!items || items.length === 0) return null;
  return (
    <ul className={`vb-note-list ${cls || ""}`}>
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}

function SignalRow({ label, value }) {
  const isTrue = value === true;
  const isFalse = value === false;
  return (
    <div className="vb-signal-row">
      <span className="vb-signal-label">{label}</span>
      <span className={`vb-signal-value ${isTrue ? "vb-yes" : isFalse ? "vb-no" : "vb-neutral"}`}>
        {isTrue ? "Yes" : isFalse ? "No" : String(value ?? "—")}
      </span>
    </div>
  );
}

function SubSectionCard({ title, detected, children }) {
  if (!detected) return null;
  return (
    <div className="vb-subsection-card">
      <span className="vb-subsection-title">{title}</span>
      {children}
    </div>
  );
}

function AssetChip({ label, variant }) {
  return (
    <span className={`vb-preview-asset-chip vb-preview-asset-chip-${variant}`}>
      {label}
    </span>
  );
}

function PreviewAssetCard({ asset }) {
  const chips = [];
  if (asset.browser_preview_ready)   chips.push(<AssetChip key="ready"      label="Browser asset ready"       variant="ready"       />);
  if (asset.browser_preview_candidate && !asset.browser_preview_ready)
                                     chips.push(<AssetChip key="candidate"   label="Preview candidate"         variant="candidate"   />);
  if (asset.engineering_only)        chips.push(<AssetChip key="eng"         label="Engineering-only"          variant="engineering" />);
  if (asset.execution_blocked)       chips.push(<AssetChip key="blocked"     label="Execution blocked"         variant="blocked"     />);
  if (asset.requires_conversion)     chips.push(<AssetChip key="conv"        label="Conversion/parser required" variant="conversion" />);
  if (asset.requires_external_tool)  chips.push(<AssetChip key="ext"         label="External tool required"    variant="external"    />);

  const cardVariant = asset.execution_blocked ? "blocked"
    : asset.browser_preview_ready             ? "ready"
    : asset.engineering_only                  ? "engineering"
    : "default";

  return (
    <div className={`vb-preview-asset-card vb-preview-asset-card-${cardVariant}`}>
      <div className="vb-preview-asset-path omni-ds-path">{asset.path}</div>
      <div className="vb-preview-asset-kind">{asset.kind}</div>
      {chips.length > 0 && <div className="vb-preview-asset-chips">{chips}</div>}
      {asset.notes && asset.notes.length > 0 && (
        <ul className="vb-preview-asset-notes">
          {asset.notes.map((n, i) => <li key={i}>{n}</li>)}
        </ul>
      )}
    </div>
  );
}

function PreviewAssetContract({ manifest, summary, previewAssets }) {
  const assets = Array.isArray(previewAssets) ? previewAssets : [];

  const readyCount     = summary?.browser_preview_ready_count    ?? manifest?.browser_preview_ready_count    ?? null;
  const candidateCount = summary?.browser_preview_candidate_count ?? manifest?.browser_preview_candidate_count ?? null;
  const engCount       = summary?.engineering_only_count          ?? manifest?.engineering_only_count          ?? null;
  const blockedCount   = summary?.execution_blocked_count         ?? manifest?.execution_blocked_count         ?? null;

  const hasCounts = readyCount !== null || candidateCount !== null || engCount !== null || blockedCount !== null;

  if (!hasCounts && assets.length === 0) return null;

  return (
    <VbSection label="Preview Asset Contract">
      {hasCounts && (
        <div className="vb-preview-asset-counts">
          {readyCount !== null && (
            <span className="vb-preview-count vb-preview-count-ready">
              {readyCount} browser ready
            </span>
          )}
          {candidateCount !== null && (
            <span className="vb-preview-count vb-preview-count-candidate">
              {candidateCount} candidate
            </span>
          )}
          {engCount !== null && (
            <span className="vb-preview-count vb-preview-count-engineering">
              {engCount} engineering-only
            </span>
          )}
          {blockedCount !== null && (
            <span className="vb-preview-count vb-preview-count-blocked">
              {blockedCount} execution-blocked
            </span>
          )}
        </div>
      )}
      {assets.length > 0 ? (
        <div className="vb-preview-assets">
          {assets.map((asset, i) => (
            <PreviewAssetCard key={i} asset={asset} />
          ))}
        </div>
      ) : (
        <p className="vb-preview-empty">No preview assets found in export directory.</p>
      )}
    </VbSection>
  );
}

export default function VisualBayPanel({ exportResult, missionResult }) {
  const { summary, manifest } = getVisualBayData(exportResult, missionResult);

  if (!summary && !manifest) return null;

  const status          = summary?.status          ?? manifest?.status          ?? "unknown";
  const previewOnly     = summary?.preview_only    ?? manifest?.preview_only    ?? true;
  const hasCad          = summary?.has_cad         ?? manifest?.cad_preview?.has_cad ?? false;
  const hasRos2         = summary?.has_ros2        ?? manifest?.ros2_preview?.detected ?? false;
  const hasSimAssets    = summary?.has_simulation_assets ?? (manifest?.simulation?.status !== "not_available") ?? false;
  const browserReady    = summary?.browser_preview_ready ?? manifest?.cad_preview?.browser_preview_ready ?? false;
  const safeToLaunch    = false; // always false per spec

  const fusion360   = manifest?.fusion360    || null;
  const cadquery    = manifest?.cadquery     || null;
  const ros2        = manifest?.ros2_preview || null;
  const simulation  = manifest?.simulation   || null;
  const blockedActions = manifest?.blocked_actions || [];
  const safetyNotes    = manifest?.safety_notes    || [];
  const nextSteps      = manifest?.next_steps      || [];

  const hasFullDetail = !!(fusion360 || cadquery || ros2 || simulation);

  const previewAssets = Array.isArray(manifest?.preview_assets)
    ? manifest.preview_assets
    : Array.isArray(summary?.preview_assets)
      ? summary.preview_assets
      : [];

  if (status === "failed") {
    return (
      <div className="visual-bay-panel visual-bay-panel-failed omni-ds-panel omni-ds-theme-visual-bay">
        <div className="vb-hud-bar">
          <span className="vb-hud-label">Visual Bay Manifest</span>
        </div>
        <p className="vb-fail-note">
          Visual Bay manifest failed: {summary?.error || "unknown error"}.
        </p>
      </div>
    );
  }

  return (
    <div className={`visual-bay-panel visual-bay-panel-${status} omni-ds-panel omni-ds-theme-visual-bay`}>
      <div className="vb-hud-bar">
        <span className="vb-hud-label">Visual Bay Manifest</span>
        <div className="vb-hud-chips">
          <VbChip label="Preview inventory only" variant="info" />
          <VbChip label="No scripts executed" variant="info" />
          <VbChip label="Simulation launch blocked" variant="blocked" />
          {browserReady
            ? <VbChip label="Browser preview ready" variant="ready" />
            : <VbChip label="Browser preview not ready" variant="warn" />
          }
        </div>
      </div>

      <div className="vb-body">
        {/* ── Compact summary grid ── */}
        <div className="vb-meta-row">
          <div className="vb-meta-cell">
            <span className="vb-meta-label">Status</span>
            <span className="vb-meta-value">{status}</span>
          </div>
          <div className="vb-meta-cell">
            <span className="vb-meta-label">Preview only</span>
            <span className={`vb-meta-value ${previewOnly ? "vb-yes" : "vb-no"}`}>
              {previewOnly ? "Yes" : "No"}
            </span>
          </div>
          <div className="vb-meta-cell">
            <span className="vb-meta-label">CAD detected</span>
            <span className={`vb-meta-value ${hasCad ? "vb-yes" : "vb-neutral"}`}>
              {hasCad ? "Yes" : "No"}
            </span>
          </div>
          <div className="vb-meta-cell">
            <span className="vb-meta-label">ROS2 detected</span>
            <span className={`vb-meta-value ${hasRos2 ? "vb-yes" : "vb-neutral"}`}>
              {hasRos2 ? "Yes" : "No"}
            </span>
          </div>
          <div className="vb-meta-cell">
            <span className="vb-meta-label">Simulation assets</span>
            <span className={`vb-meta-value ${hasSimAssets ? "vb-yes" : "vb-neutral"}`}>
              {hasSimAssets ? "Yes" : "No"}
            </span>
          </div>
          <div className="vb-meta-cell">
            <span className="vb-meta-label">Browser preview ready</span>
            <span className={`vb-meta-value ${browserReady ? "vb-yes" : "vb-no"}`}>
              {browserReady ? "Yes" : "Browser preview not ready"}
            </span>
          </div>
          <div className="vb-meta-cell">
            <span className="vb-meta-label">Safe to launch</span>
            <span className="vb-meta-value vb-no">No</span>
          </div>
        </div>

        {/* ── Full manifest detail ── */}
        {hasFullDetail && (
          <div className="vb-detail-grid">
            <SubSectionCard title="Fusion 360" detected={fusion360?.detected}>
              <SignalRow label="Script files" value={fusion360?.script_files?.length ?? 0} />
              <SignalRow label="Parameter files" value={fusion360?.parameter_files?.length ?? 0} />
              <SignalRow label="README files" value={fusion360?.readme_files?.length ?? 0} />
              <SignalRow label="Browser preview ready" value={fusion360?.browser_preview_ready ?? false} />
              <SignalRow label="Mesh available (.stl)" value={fusion360?.mesh_available ?? false} />
              <SignalRow label="Engineering CAD (.step)" value={fusion360?.engineering_cad_available ?? false} />
            </SubSectionCard>

            <SubSectionCard title="CadQuery" detected={cadquery?.detected}>
              <SignalRow label="Script files" value={cadquery?.script_files?.length ?? 0} />
              <SignalRow label="Browser preview ready" value={cadquery?.browser_preview_ready ?? false} />
              <SignalRow label="Mesh available (.stl)" value={cadquery?.mesh_available ?? false} />
              <SignalRow label="Engineering CAD (.step)" value={cadquery?.engineering_cad_available ?? false} />
            </SubSectionCard>

            <SubSectionCard title="ROS2 Package" detected={ros2?.detected}>
              <SignalRow label="package.xml files" value={ros2?.package_xml_files?.length ?? 0} />
              <SignalRow label="URDF / Xacro files" value={ros2?.urdf_files?.length ?? 0} />
              <SignalRow label="Launch files" value={ros2?.launch_files?.length ?? 0} />
              <SignalRow label="Config files" value={ros2?.config_files?.length ?? 0} />
            </SubSectionCard>

            {simulation && simulation.status !== "not_available" && (
              <SubSectionCard title="Simulation Assets" detected={simulation.status !== "not_available"}>
                <SignalRow label="Status" value={simulation.status?.replace(/_/g, " ")} />
                <SignalRow label="Launch files" value={simulation?.launch_files?.length ?? 0} />
                <SignalRow label="World files" value={simulation?.world_files?.length ?? 0} />
                <SignalRow label="RViz files" value={simulation?.rviz_files?.length ?? 0} />
                <SignalRow label="Safe to launch" value={false} />
              </SubSectionCard>
            )}
          </div>
        )}

        {/* ── Preview asset contract ── */}
        <PreviewAssetContract manifest={manifest} summary={summary} previewAssets={previewAssets} />

        {/* ── Static viewer shell ── */}
        <VisualBayViewerShell previewAssets={previewAssets} />

        {/* ── Blocked actions ── */}
        {blockedActions.length > 0 && (
          <VbSection label="Blocked actions">
            <VbBlockedList items={blockedActions} />
          </VbSection>
        )}

        {/* ── Safety notes ── */}
        {safetyNotes.length > 0 && (
          <VbSection label="Safety notes">
            <VbNoteList items={safetyNotes} cls="vb-safety-list" />
          </VbSection>
        )}

        {/* ── Next steps ── */}
        {nextSteps.length > 0 && (
          <VbSection label="Next steps">
            <VbNoteList items={nextSteps} cls="vb-next-list" />
          </VbSection>
        )}
      </div>
    </div>
  );
}
