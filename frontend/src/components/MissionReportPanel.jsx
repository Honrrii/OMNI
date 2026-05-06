function getMissionReport(exportResult) {
  return (
    exportResult?.export?.mission_report ||
    exportResult?.mission_report ||
    null
  );
}

function getExportDirectory(exportResult) {
  return (
    exportResult?.export?.export_dir ||
    exportResult?.export_dir ||
    "No export directory returned."
  );
}

function FilePathCard({ title, description, path }) {
  if (!path) return null;

  return (
    <div className="mission-report-file-card">
      <div>
        <span className="mission-report-file-label">{title}</span>
        <p>{description}</p>
      </div>
      <code>{path}</code>
    </div>
  );
}

export default function MissionReportPanel({ exportResult }) {
  const report = getMissionReport(exportResult);
  const exportDirectory = getExportDirectory(exportResult);

  if (!report) return null;

  const exportedFileCount = Array.isArray(report.exported_files)
    ? report.exported_files.length
    : 0;

  return (
    <section className="mission-report-panel">
      <div className="mission-report-header">
        <div>
          <span className="mission-report-kicker">Mission Dossier</span>
          <h2>Mission Report Generated</h2>
          <p>
            OMNI exported a structured engineering report with artifact
            references, validation context, provenance, and human approval
            guidance.
          </p>
        </div>

        <div className="mission-report-status-pill">
          {report.status || "generated"}
        </div>
      </div>

      <div className="mission-report-summary-grid">
        <div className="mission-report-stat-card">
          <span>Export Folder</span>
          <code>{exportDirectory}</code>
        </div>

        <div className="mission-report-stat-card">
          <span>Mission Slug</span>
          <code>{report.mission_slug || "not provided"}</code>
        </div>

        <div className="mission-report-stat-card">
          <span>Tracked Files</span>
          <strong>{exportedFileCount}</strong>
        </div>
      </div>

      <div className="mission-report-file-grid">
        <FilePathCard
          title="OMNI Mission Report"
          description="Human-readable mission dossier for engineering review."
          path={report.report_file}
        />

        <FilePathCard
          title="Artifact Manifest"
          description="Structured index of exported mission artifacts."
          path={report.artifact_manifest}
        />

        <FilePathCard
          title="Provenance Record"
          description="Record of mission intent, generation, validation, and review stages."
          path={report.provenance_record}
        />
      </div>

      <div className="mission-report-note">
        <strong>Human approval required:</strong> Review generated CAD, ROS2,
        power, fabrication, and safety assumptions before using outputs on
        physical hardware.
      </div>
    </section>
  );
}