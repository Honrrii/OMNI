import { useEffect, useState } from "react";
import { getRosStatus } from "../api/rosApi";

function SimStatusBadge({ active, label }) {
  return (
    <span className={`sim-status-badge ${active ? "active" : "inactive"}`}>
      {active ? "✓" : "•"} {label}
    </span>
  );
}

function SimSection({ title, children }) {
  return (
    <section className="sim-section">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

function SimList({ items, emptyText }) {
  if (!items || items.length === 0) {
    return <p className="sim-muted">{emptyText}</p>;
  }

  return (
    <ul className="sim-list">
      {items.map((item, index) => (
        <li key={`${item}-${index}`}>
          <code>{item}</code>
        </li>
      ))}
    </ul>
  );
}

export default function OmniSimulationPanel() {
  const [rosStatus, setRosStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [error, setError] = useState("");

  async function refreshRosStatus() {
    setLoading(true);
    setError("");

    try {
      const data = await getRosStatus();
      setRosStatus(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    getRosStatus()
      .then(data => { if (!cancelled) setRosStatus(data); })
      .catch(err => { if (!cancelled) setError(err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!autoRefresh) {
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      refreshRosStatus();
    }, 3000);

    return () => window.clearInterval(intervalId);
  }, [autoRefresh]);

  const processes = rosStatus?.processes || {};

  return (
    <div className="sim-panel">
      <div className="sim-header">
        <div>
          <p className="sim-eyebrow">OMNI Simulation</p>
          <h2>ROS2 Mission Control</h2>
          <p className="sim-subtitle">
            Read-only ROS2/Gazebo/RViz status dashboard. This panel checks nodes,
            topics, and visualization processes without controlling hardware.
          </p>
        </div>

      </div>

      <div className="sim-actions">
        <button type="button" onClick={refreshRosStatus} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh ROS Status"}
        </button>

        <button
          type="button"
          className={autoRefresh ? "active" : ""}
          onClick={() => setAutoRefresh((value) => !value)}
        >
          {autoRefresh ? "Auto Refresh On" : "Auto Refresh Off"}
        </button>
      </div>

      {error && <div className="sim-error">{error}</div>}

      <div className="sim-grid">
        <SimSection title="System State">
          <p>
            <strong>Simulation State:</strong>{" "}
            {rosStatus?.simulation_state || "unknown"}
          </p>
          <p>
            <strong>Node Count:</strong> {rosStatus?.node_count ?? 0}
          </p>
          <p>
            <strong>Topic Count:</strong> {rosStatus?.topic_count ?? 0}
          </p>
          <p>
            <strong>Physical Robot Control:</strong>{" "}
            {rosStatus?.physical_robot_control ? "Enabled" : "Disabled"}
          </p>
          <p className="sim-muted">{rosStatus?.safety_note}</p>
        </SimSection>

        <SimSection title="Visualization Processes">
          <div className="sim-status-row">
            <SimStatusBadge active={processes.rviz_detected} label="RViz" />
            <SimStatusBadge active={processes.gazebo_detected} label="Gazebo" />
            <SimStatusBadge active={processes.rosbridge_detected} label="rosbridge" />
            <SimStatusBadge active={processes.foxglove_bridge_detected} label="Foxglove" />
          </div>

          <SimList
            items={processes.matching_processes}
            emptyText="No RViz/Gazebo/bridge processes detected."
          />
        </SimSection>

        <SimSection title="Active ROS2 Nodes">
          <SimList
            items={rosStatus?.nodes}
            emptyText="No active ROS2 nodes detected yet."
          />
        </SimSection>

        <SimSection title="Active ROS2 Topics">
          <SimList
            items={rosStatus?.topics}
            emptyText="No active ROS2 topics detected yet."
          />
        </SimSection>

        <SimSection title="Recommended Next Steps">
          <ul className="sim-list text-list">
            {(rosStatus?.recommended_next_steps || [
              "Start ROS2 or Gazebo to populate this dashboard.",
            ]).map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </SimSection>

        <SimSection title="Future Levels">
          <ul className="sim-list text-list">
            <li>Level 2: Camera and sensor feed panel.</li>
            <li>Level 3: RViz-like robot visualization panel.</li>
            <li>Level 4: Gazebo launch and simulation controls.</li>
            <li>Level 5: Mission-controlled sim-to-CAD workflow.</li>
          </ul>
        </SimSection>
      </div>
    </div>
  );
}