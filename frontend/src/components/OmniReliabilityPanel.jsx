import { useMemo, useState } from "react";

const API_ROOT = "http://127.0.0.1:8000";

const ROVER_CONTEXT = {
  power_budget: {
    battery_voltage_v: 7.4,
    battery_capacity_mah: 2200,
    average_current_a: 1.2,
    peak_current_a: 3.0,
  },
  rover_mobility: {
    mass_kg: 1.5,
    wheel_radius_m: 0.04,
    motor_stall_torque_nm: 0.4,
    motor_count: 4,
    drivetrain_efficiency: 0.75,
    target_incline_deg: 10.0,
    rolling_resistance_coeff: 0.03,
    safety_factor: 1.5,
  },
};

const DRONE_CONTEXT = {
  drone_sizing: {
    estimated_total_mass_g: 850,
    motor_count: 4,
    max_thrust_per_motor_g: 650,
    battery_capacity_mah: 2200,
    battery_voltage_v: 11.1,
    average_current_per_motor_a: 4.5,
    payload_mass_g: 120,
  },
};

const DEFAULT_MANUAL_PAYLOAD = {
  mission_text:
    "Design a palm-sized autonomous rover with ROS2, camera perception, battery power, Fusion 360 CAD, and validation gates.",
  context: ROVER_CONTEXT,
};

function statusClass(status) {
  return String(status || "WARN").toLowerCase();
}

function getMissionText(missionResult) {
  return (
    missionResult?.fullMission ||
    missionResult?.raw?.mission ||
    missionResult?.title ||
    ""
  );
}

function inferContextFromMission(missionText) {
  const text = String(missionText || "").toLowerCase();

  if (
    text.includes("drone") ||
    text.includes("quadcopter") ||
    text.includes("hexacopter") ||
    text.includes("uav")
  ) {
    return DRONE_CONTEXT;
  }

  if (
    text.includes("rover") ||
    text.includes("ugv") ||
    text.includes("wheeled robot") ||
    text.includes("tracked robot")
  ) {
    return ROVER_CONTEXT;
  }

  return {};
}

function buildLatestMissionPayload({ missionResult, exportResult, context }) {
  const missionText = getMissionText(missionResult);

  if (!missionText.trim()) {
    throw new Error("No latest mission is loaded. Run a mission first.");
  }

  const payload = {
    mission_text: missionText,
    mission_result: missionResult?.raw || missionResult || null,
  };

  if (exportResult) {
    payload.export_result = exportResult;
  }

  if (context && Object.keys(context).length > 0) {
    payload.context = context;
  }

  return payload;
}

export default function OmniReliabilityPanel({ missionResult, exportResult }) {
  const latestMissionText = getMissionText(missionResult);

  const inferredContext = useMemo(() => {
    return inferContextFromMission(latestMissionText);
  }, [latestMissionText]);

  const [payloadText, setPayloadText] = useState(
    JSON.stringify(DEFAULT_MANUAL_PAYLOAD, null, 2)
  );

  const [contextText, setContextText] = useState(
    JSON.stringify(inferredContext, null, 2)
  );

  const [report, setReport] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  function parseJsonBlock(text, fallback = {}) {
    const trimmed = String(text || "").trim();

    if (!trimmed) {
      return fallback;
    }

    return JSON.parse(trimmed);
  }

  async function submitReliabilityPayload(payload) {
    setStatus("loading");
    setError("");
    setReport(null);

    try {
      const response = await fetch(`${API_ROOT}/api/reliability/review`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Reliability review failed.");
      }

      setReport(data);
      setStatus("done");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }

  async function runManualReliabilityReview() {
    try {
      const payload = parseJsonBlock(payloadText);
      await submitReliabilityPayload(payload);
    } catch (err) {
      setError(`Invalid manual JSON: ${err.message}`);
      setStatus("error");
    }
  }

  async function runLatestMissionReview() {
    try {
      const context = parseJsonBlock(contextText, {});

      const payload = buildLatestMissionPayload({
        missionResult,
        exportResult,
        context,
      });

      setPayloadText(JSON.stringify(payload, null, 2));
      await submitReliabilityPayload(payload);
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }

  function loadLatestMissionPayload() {
    try {
      const context = parseJsonBlock(contextText, {});

      const payload = buildLatestMissionPayload({
        missionResult,
        exportResult,
        context,
      });

      setPayloadText(JSON.stringify(payload, null, 2));
      setError("");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }

  function loadDroneExample() {
    const dronePayload = {
      mission_text:
        "Design a quadcopter drone with Fusion 360 CAD, ROS2 validation, camera payload, battery power, and OMNITorch visual review.",
      context: DRONE_CONTEXT,
    };

    setPayloadText(JSON.stringify(dronePayload, null, 2));
    setContextText(JSON.stringify(DRONE_CONTEXT, null, 2));
  }

  function loadRoverExample() {
    setPayloadText(JSON.stringify(DEFAULT_MANUAL_PAYLOAD, null, 2));
    setContextText(JSON.stringify(ROVER_CONTEXT, null, 2));
  }

  function loadInferredContext() {
    setContextText(JSON.stringify(inferredContext, null, 2));
  }

  const hasLatestMission = Boolean(latestMissionText.trim());

  return (
    <section className="reliability-panel">
      <div className="reliability-card">
        <p className="eyebrow">Reliability Core v0.1</p>
        <h2>Engineering Reliability Review</h2>

        <p className="muted">
          Review the latest OMNI mission automatically, or use manual JSON for
          calculator and regression testing.
        </p>

        <div className="latest-mission-card">
          <p className="eyebrow">Latest Mission Status</p>
          {hasLatestMission ? (
            <>
              <h3>{missionResult?.title || "Latest OMNI Mission Loaded"}</h3>
              <p>{latestMissionText}</p>
              <p className="muted">
                Export result: {exportResult ? "available" : "not available yet"}
              </p>
            </>
          ) : (
            <p className="muted">
              No mission is currently loaded. Run a mission from Command first,
              then return here and click Review Latest Mission.
            </p>
          )}
        </div>

        <div className="console-actions">
          <button
            className="primary-button"
            onClick={runLatestMissionReview}
            disabled={!hasLatestMission || status === "loading"}
          >
            {status === "loading" ? "Reviewing..." : "Review Latest Mission"}
          </button>

          <button
            className="secondary-button"
            onClick={loadLatestMissionPayload}
            disabled={!hasLatestMission}
          >
            Load Latest Payload
          </button>

          <button className="secondary-button" onClick={loadInferredContext}>
            Infer Calculator Context
          </button>
        </div>

        <div className="console-actions">
          <button className="secondary-button" onClick={loadRoverExample}>
            Load Rover Example
          </button>

          <button className="secondary-button" onClick={loadDroneExample}>
            Load Drone Example
          </button>
        </div>

        <label className="reliability-label">
          Calculator Context
          <span>
            Use verified values when possible. These values become calculation
            evidence in Reliability Core.
          </span>
        </label>

        <textarea
          className="reliability-json-input reliability-context-input"
          value={contextText}
          onChange={(event) => setContextText(event.target.value)}
          placeholder='Example: { "drone_sizing": { ... } }'
        />

        <label className="reliability-label">
          Manual Review Payload
          <span>
            This is useful for debugging. The latest mission button builds this
            automatically from OMNI state.
          </span>
        </label>

        <textarea
          className="reliability-json-input"
          value={payloadText}
          onChange={(event) => setPayloadText(event.target.value)}
        />

        <button
          className="primary-button reliability-run-button"
          onClick={runManualReliabilityReview}
          disabled={status === "loading"}
        >
          {status === "loading" ? "Reviewing..." : "Run Manual JSON Review"}
        </button>

        {error && <p className="error-message">{error}</p>}
      </div>

      {report && (
        <div className="reliability-results">
          <div className={`reliability-summary ${statusClass(report.overall_status)}`}>
            <div>
              <p className="eyebrow">Overall Status</p>
              <h1>{report.overall_status}</h1>
              <p>{report.summary}</p>
            </div>

            <div className="confidence-ring">
              {(report.engineering_confidence * 100).toFixed(1)}%
            </div>
          </div>

          <div className="reliability-grid">
            <div className="panel">
              <p className="eyebrow">Gates</p>
              <h2>Engineering Checks</h2>

              <div className="gate-list">
                {report.gates.map((gate) => (
                  <article
                    key={gate.id}
                    className={`gate-card ${statusClass(gate.status)}`}
                  >
                    <div className="gate-topline">
                      <strong>{gate.name}</strong>
                      <span>{gate.status}</span>
                    </div>

                    <p>{gate.summary}</p>

                    {gate.warnings?.length > 0 && (
                      <ul>
                        {gate.warnings.map((warning, index) => (
                          <li key={index}>{warning}</li>
                        ))}
                      </ul>
                    )}

                    {gate.blockers?.length > 0 && (
                      <ul>
                        {gate.blockers.map((blocker, index) => (
                          <li key={index}>{blocker}</li>
                        ))}
                      </ul>
                    )}
                  </article>
                ))}
              </div>
            </div>

            <div className="panel">
              <p className="eyebrow">Evidence</p>
              <h2>Proof Records</h2>

              <div className="evidence-list">
                {report.evidence.map((item) => (
                  <article
                    key={item.id}
                    className={`evidence-card ${statusClass(item.status)}`}
                  >
                    <div className="gate-topline">
                      <strong>{item.label}</strong>
                      <span>{item.status}</span>
                    </div>

                    <p>
                      <strong>Type:</strong> {item.evidence_type}
                    </p>
                    <p>
                      <strong>Source:</strong> {item.source}
                    </p>
                    <p>
                      <strong>Confidence:</strong> {item.confidence}
                    </p>
                    {item.human_review_required && (
                      <p className="muted">Human review required.</p>
                    )}
                  </article>
                ))}
              </div>
            </div>

            <div className="panel wide-panel">
              <p className="eyebrow">Warnings + Blockers</p>
              <h2>What still needs attention?</h2>

              <h3>Warnings</h3>
              <ul className="clean-list">
                {report.warnings.length > 0 ? (
                  report.warnings.map((warning, index) => (
                    <li key={index}>{warning}</li>
                  ))
                ) : (
                  <li>No warnings returned.</li>
                )}
              </ul>

              <h3>Blockers</h3>
              <ul className="clean-list">
                {report.blockers.length > 0 ? (
                  report.blockers.map((blocker, index) => (
                    <li key={index}>{blocker}</li>
                  ))
                ) : (
                  <li>No blockers returned.</li>
                )}
              </ul>
            </div>

            <div className="panel wide-panel">
              <p className="eyebrow">Next Tests</p>
              <h2>Required Validation Steps</h2>

              <ul className="clean-list">
                {report.required_next_tests.length > 0 ? (
                  report.required_next_tests.map((test, index) => (
                    <li key={index}>{test}</li>
                  ))
                ) : (
                  <li>No required next tests returned.</li>
                )}
              </ul>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}