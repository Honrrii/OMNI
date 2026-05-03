import { useState } from "react";
import {
  validateForgeMission,
  generateForgeCadScript,
  executeForgeCadScript,
} from "../api/forgeApi";

const DEFAULT_FORGE_PROMPT =
  "Design a printable Raspberry Pi camera mount for monitoring my 3D printer. It should be PLA, screw-mounted, angled downward 25 degrees, and include a safety/fabrication review. Do not start any print.";

function StatusBadge({ status }) {
  const cleanStatus = status || "idle";

  return (
    <span className={`forge-badge forge-badge-${cleanStatus}`}>
      {cleanStatus}
    </span>
  );
}

function Section({ title, children }) {
  return (
    <section className="forge-section">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

function ListBlock({ items }) {
  if (!items || items.length === 0) {
    return <p className="forge-muted">None reported.</p>;
  }

  return (
    <ul className="forge-list">
      {items.map((item, index) => (
        <li key={`${item}-${index}`}>{item}</li>
      ))}
    </ul>
  );
}

function JsonBlock({ data }) {
  if (!data) {
    return <p className="forge-muted">No data available.</p>;
  }

  return <pre className="forge-json">{JSON.stringify(data, null, 2)}</pre>;
}

export default function OmniForgePanel() {
  const [mission, setMission] = useState(DEFAULT_FORGE_PROMPT);
  const [forgeResult, setForgeResult] = useState(null);
  const [cadScriptResult, setCadScriptResult] = useState(null);
  const [executionResult, setExecutionResult] = useState(null);
  const [loadingAction, setLoadingAction] = useState("");
  const [error, setError] = useState("");

  const validationReport = forgeResult?.report || cadScriptResult?.report;
  const cadPlan = validationReport?.cad_plan;
  const generatedScriptPath = cadScriptResult?.cad_script?.script_path;
  const exportedFiles = executionResult?.execution_result?.exported_files || [];
  const artifactManifest = executionResult?.artifact_package?.manifest;

  async function handleValidate() {
    setError("");
    setLoadingAction("validate");
    setExecutionResult(null);

    try {
      const result = await validateForgeMission(mission);
      setForgeResult(result);
      setCadScriptResult(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingAction("");
    }
  }

  async function handleGenerateCadScript() {
    setError("");
    setLoadingAction("generate-script");
    setExecutionResult(null);

    try {
      const result = await generateForgeCadScript(mission);
      setCadScriptResult(result);
      setForgeResult(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingAction("");
    }
  }

  async function handleExecuteCadScript() {
    if (!generatedScriptPath) {
      setError("Generate a CAD script first.");
      return;
    }

    setError("");
    setLoadingAction("execute-script");

    try {
      const result = await executeForgeCadScript(generatedScriptPath);
      setExecutionResult(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingAction("");
    }
  }

  return (
    <div className="forge-panel">
      <div className="forge-header">
        <div>
          <p className="forge-eyebrow">OMNI Forge</p>
          <h2>Workshop Artifact Pipeline</h2>
          <p className="forge-subtitle">
            Validate missions, plan CAD parameters, generate CadQuery scripts,
            export STEP/STL files, and package artifacts for human review.
          </p>
        </div>

        <StatusBadge
          status={
            executionResult?.status ||
            cadScriptResult?.status ||
            forgeResult?.status ||
            "idle"
          }
        />
      </div>

      <textarea
        className="forge-textarea"
        value={mission}
        onChange={(event) => setMission(event.target.value)}
        placeholder="Describe a printable workshop part..."
      />

      <div className="forge-actions">
        <button
          type="button"
          onClick={handleValidate}
          disabled={Boolean(loadingAction)}
        >
          {loadingAction === "validate" ? "Validating..." : "Run Validation"}
        </button>

        <button
          type="button"
          onClick={handleGenerateCadScript}
          disabled={Boolean(loadingAction)}
        >
          {loadingAction === "generate-script"
            ? "Generating..."
            : "Generate CAD Script"}
        </button>

        <button
          type="button"
          onClick={handleExecuteCadScript}
          disabled={Boolean(loadingAction) || !generatedScriptPath}
        >
          {loadingAction === "execute-script" ? "Exporting..." : "Export STEP/STL"}
        </button>
      </div>

      {error && <div className="forge-error">{error}</div>}

      <div className="forge-grid">
        <Section title="Mission Status">
          <p>
            <strong>Forge Level:</strong>{" "}
            {executionResult?.forge_level ||
              cadScriptResult?.forge_level ||
              forgeResult?.forge_level ||
              "Not run yet"}
          </p>
          <p>
            <strong>Validation:</strong>{" "}
            {validationReport?.status || "Not run yet"}
          </p>
          <p>
            <strong>Human Approval:</strong>{" "}
            {validationReport?.mission?.requires_human_approval
              ? "Required"
              : "Unknown"}
          </p>
          <p>
            <strong>Physical Execution:</strong>{" "}
            {executionResult?.execution_result?.physical_execution_performed
              ? "Performed"
              : "Not performed"}
          </p>
        </Section>

        <Section title="Warnings">
          <ListBlock
            items={[
              ...(validationReport?.warnings || []),
              ...(cadPlan?.warnings || []),
            ]}
          />
        </Section>

        <Section title="CAD Parameter Plan">
          {cadPlan ? (
            <>
              <p>
                <strong>Part:</strong> {cadPlan.part_type}
              </p>
              <p>
                <strong>Backend:</strong> {cadPlan.cad_backend}
              </p>
              <p>
                <strong>Ready for Script:</strong>{" "}
                {cadPlan.ready_for_script_generation ? "Yes" : "No"}
              </p>
              <JsonBlock data={cadPlan.parameters} />
            </>
          ) : (
            <p className="forge-muted">No CAD plan generated yet.</p>
          )}
        </Section>

        <Section title="Generated Script">
          {generatedScriptPath ? (
            <>
              <p>
                <strong>Script Path:</strong>
              </p>
              <code className="forge-code-line">{generatedScriptPath}</code>
              <p className="forge-muted">
                Script generation does not run printers or fabrication tools.
              </p>
            </>
          ) : (
            <p className="forge-muted">No generated script yet.</p>
          )}
        </Section>

        <Section title="Exported CAD Files">
          {exportedFiles.length > 0 ? (
            <div className="forge-file-list">
              {exportedFiles.map((file) => (
                <div className="forge-file-card" key={file.path}>
                  <strong>{file.filename}</strong>
                  <span>{file.suffix}</span>
                  <span>{file.size_bytes} bytes</span>
                  <code>{file.path}</code>
                </div>
              ))}
            </div>
          ) : (
            <p className="forge-muted">No STEP/STL exports yet.</p>
          )}
        </Section>

        <Section title="Artifact Manifest">
          {artifactManifest ? (
            <>
              <p>
                <strong>Manifest:</strong>
              </p>
              <code className="forge-code-line">
                {artifactManifest.manifest_path}
              </code>
              <p>
                <strong>Ready for Fabrication Review:</strong>{" "}
                {artifactManifest.ready_for_fabrication_review ? "Yes" : "No"}
              </p>
              <p>
                <strong>Fabrication Started:</strong>{" "}
                {artifactManifest.safety_status?.fabrication_started
                  ? "Yes"
                  : "No"}
              </p>
            </>
          ) : (
            <p className="forge-muted">No artifact manifest yet.</p>
          )}
        </Section>
      </div>
    </div>
  );
}