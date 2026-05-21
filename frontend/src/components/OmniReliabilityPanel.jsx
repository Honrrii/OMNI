import { useState } from "react";

const API_ROOT = "http://127.0.0.1:8000";

const DEFAULT_PAYLOAD = {
  mission_text:
    "Design a palm-sized autonomous rover with ROS2, camera perception, battery power, Fusion 360 CAD, and validation gates.",
  context: {
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
  },
};

function statusClass(status) {
  return String(status || "WARN").toLowerCase();
}

export default function OmniReliabilityPanel() {
  const [payloadText, setPayloadText] = useState(
    JSON.stringify(DEFAULT_PAYLOAD, null, 2)
  );
  const [report, setReport] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  async function runReliabilityReview() {
    setStatus("loading");
    setError("");
    setReport(null);

    try {
      const payload = JSON.parse(payloadText);

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

  function loadDroneExample() {
    const dronePayload = {
      mission_text:
        "Design a quadcopter drone with Fusion 360 CAD, ROS2 validation, camera payload, battery power, and OMNITorch visual review.",
      context: {
        drone_sizing: {
          estimated_total_mass_g: 850,
          motor_count: 4,
          max_thrust_per_motor_g: 650,
          battery_capacity_mah: 2200,
          battery_voltage_v: 11.1,
          average_current_per_motor_a: 4.5,
          payload_mass_g: 120,
        },
      },
    };

    setPayloadText(JSON.stringify(dronePayload, null, 2));
  }

  function loadRoverExample() {
    setPayloadText(JSON.stringify(DEFAULT_PAYLOAD, null, 2));
  }

  return (
    <section className="reliability-panel">
      <div className="reliability-card">
        <p className="eyebrow">Reliability Core v0.1</p>
        <h2>Engineering Reliability Review</h2>
        <p className="muted">
          Run evidence-labeled pass/warn/fail/blocker review against OMNI
          missions, calculator context, export validation, and OMNITorch output.
        </p>

        <div className="console-actions">
          <button className="secondary-button" onClick={loadRoverExample}>
            Load Rover Example
          </button>
          <button className="secondary-button" onClick={loadDroneExample}>
            Load Drone Example
          </button>
        </div>

        <textarea
          className="reliability-json-input"
          value={payloadText}
          onChange={(event) => setPayloadText(event.target.value)}
        />

        <button
          className="primary-button reliability-run-button"
          onClick={runReliabilityReview}
          disabled={status === "loading"}
        >
          {status === "loading" ? "Reviewing..." : "Run Reliability Review"}
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