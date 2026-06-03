import { useState, useEffect } from "react";

// ── Stage definitions ────────────────────────────────────────────────────────

const STAGES_MISSION = [
  { id: "echo",       label: "Echo parsing mission intent"  },
  { id: "planning",   label: "Core planning active"         },
  { id: "agents",     label: "Agent orchestration active"   },
  { id: "validation", label: "Validation gates aligning"    },
  { id: "export",     label: "Export sequence preparing"    },
];

const STAGES_IDEA = [
  { id: "echo",       label: "Echo interpreting concept"    },
  { id: "planning",   label: "Core planning active"         },
  { id: "agents",     label: "Agent orchestration active"   },
  { id: "validation", label: "Validation gates aligning"    },
  { id: "export",     label: "Export sequence preparing"    },
];

// ── Timing helpers ───────────────────────────────────────────────────────────

function computeIntensity(elapsed) {
  if (elapsed < 0)  return 0.10;
  if (elapsed < 15) return 0.10 + (elapsed / 15) * 0.25;
  if (elapsed < 30) return 0.35 + ((elapsed - 15) / 15) * 0.25;
  if (elapsed < 60) return 0.60 + ((elapsed - 30) / 30) * 0.20;
  if (elapsed < 90) return 0.80 + ((elapsed - 60) / 30) * 0.13;
  return 0.95;
}

function computeActiveStage(elapsed) {
  if (elapsed < 15) return 0;
  if (elapsed < 30) return 1;
  if (elapsed < 60) return 2;
  if (elapsed < 90) return 3;
  return 4;
}

function formatElapsed(elapsed) {
  const m = Math.floor(elapsed / 60);
  const s = elapsed % 60;
  return m > 0 ? `${m}m ${String(s).padStart(2, "0")}s` : `${s}s`;
}

// ── Engine sub-components ────────────────────────────────────────────────────

function IntakeBar({ widthPct }) {
  return (
    <div
      className="henry-intake-bar"
      style={{ width: `${widthPct}%` }}
      aria-hidden="true"
    />
  );
}

function NozzleBar({ widthPct }) {
  return (
    <div
      className="henry-nozzle-bar"
      style={{ width: `${widthPct}%` }}
      aria-hidden="true"
    />
  );
}

function EngineBody() {
  return (
    <div className="henry-engine-body" aria-hidden="true">
      {/* Compressor intake — bars widen toward chamber */}
      <div className="henry-engine-intake">
        <IntakeBar widthPct={32} />
        <IntakeBar widthPct={52} />
        <IntakeBar widthPct={72} />
        <IntakeBar widthPct={90} />
      </div>

      {/* Combustion chamber */}
      <div className="henry-engine-chamber">
        <div className="henry-core">
          <div className="henry-core-ring henry-core-ring-3" />
          <div className="henry-core-ring henry-core-ring-2" />
          <div className="henry-core-ring henry-core-ring-1" />
          <div className="henry-core-dot" />
        </div>
      </div>

      {/* Nozzle — bars narrow away from chamber */}
      <div className="henry-engine-nozzle">
        <NozzleBar widthPct={90} />
        <NozzleBar widthPct={65} />
        <NozzleBar widthPct={42} />
      </div>
    </div>
  );
}

function ExhaustPlume({ intensity }) {
  const opacity = Math.min(0.15 + intensity * 0.80, 0.90);
  const height  = Math.round(24 + intensity * 72);
  return (
    <div className="henry-exhaust" aria-hidden="true">
      <div
        className="henry-exhaust-plume"
        style={{ opacity, height: `${height}px` }}
      />
      <div
        className="henry-exhaust-core-stream"
        style={{ opacity: opacity * 0.7 }}
      />
    </div>
  );
}

function StageChip({ label, state }) {
  return (
    <span className={`henry-stage-chip henry-stage-${state}`}>
      {state === "done"   && <span className="henry-stage-icon" aria-hidden="true">✓ </span>}
      {state === "active" && <span className="henry-stage-icon" aria-hidden="true">▶ </span>}
      {state === "pending" && <span className="henry-stage-icon" aria-hidden="true">· </span>}
      {label}
    </span>
  );
}

function TelemetryCell({ label, value }) {
  return (
    <div className="henry-telem-cell">
      <span className="henry-telem-label">{label}</span>
      <span className="henry-telem-value">{value}</span>
    </div>
  );
}

function IntensityBar({ intensity }) {
  return (
    <div className="henry-intensity-bar-wrap" aria-label={`Processing intensity ${Math.round(intensity * 100)}%`}>
      <div className="henry-intensity-track">
        <div
          className="henry-intensity-fill"
          style={{ width: `${Math.round(intensity * 100)}%` }}
        />
      </div>
      <span className="henry-intensity-pct">{Math.round(intensity * 100)}%</span>
      {/* Accessible text alternative to color */}
      <span className="henry-intensity-label">processing intensity</span>
    </div>
  );
}

// ── Root component ───────────────────────────────────────────────────────────

export default function HenryEngineLoader({
  isRunning   = false,
  missionText = "",
  commandMode = "mission",
  joke        = null,
}) {
  const [elapsed, setElapsed] = useState(0);

  // Component only mounts while loading is true; state resets naturally on unmount.
  useEffect(() => {
    if (!isRunning) return;
    const timer = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, [isRunning]);

  const intensity    = computeIntensity(elapsed);
  const activeStage  = computeActiveStage(elapsed);
  const stages       = commandMode === "idea" ? STAGES_IDEA : STAGES_MISSION;

  const cssVars = {
    "--he-intensity":    intensity,
    "--he-glow-radius":  `${Math.round(8 + intensity * 44)}px`,
    "--he-core-opacity": Math.min(0.35 + intensity * 0.65, 1),
  };

  const preview = missionText
    ? missionText.trim().slice(0, 90) + (missionText.trim().length > 90 ? "…" : "")
    : null;

  return (
    <div
      className="henry-loader"
      style={cssVars}
      role="status"
      aria-live="polite"
      aria-label="OMNI processing mission — Henry Engine ignition sequence active"
    >
      <div className="henry-loader-card">

        {/* ── Header ── */}
        <div className="henry-loader-header">
          <p className="henry-eyebrow">HENRY ENGINE</p>
          <h2 className="henry-title">Mission Ignition Sequence</h2>
          {preview && (
            <p className="henry-mission-preview">{preview}</p>
          )}
        </div>

        {/* ── Engine visualization ── */}
        <div className="henry-engine" aria-hidden="true">
          <EngineBody />
          <ExhaustPlume intensity={intensity} />
        </div>

        {/* ── Intensity bar ── */}
        <IntensityBar intensity={intensity} />

        {/* ── Telemetry ── */}
        <div className="henry-telemetry" aria-label="Engine telemetry readout">
          <TelemetryCell label="ELAPSED"   value={formatElapsed(elapsed)} />
          <TelemetryCell label="STAGE"     value={`${activeStage + 1} / ${stages.length}`} />
          <TelemetryCell label="INTENSITY" value={`${Math.round(intensity * 100)}%`} />
          <TelemetryCell label="STATUS"    value="ACTIVE" />
        </div>

        {/* ── Stage chips ── */}
        <div className="henry-stage-row" aria-label="Mission stages">
          {stages.map((stage, i) => {
            const state =
              i < activeStage  ? "done"   :
              i === activeStage ? "active" :
              "pending";
            return (
              <StageChip key={stage.id} label={stage.label} state={state} />
            );
          })}
        </div>

        {/* ── Morbid runtime humor (preserves existing personality) ── */}
        {joke && (
          <div className="henry-joke-card">
            <p className="henry-eyebrow">Morbid Runtime Humor</p>
            <p className="henry-joke-text">{joke}</p>
          </div>
        )}

        {/* ── Safety note ── */}
        <p className="henry-safety-note">
          Visual processing animation only. No real propulsion, simulation, flight readiness,
          or engineering validation implied.
        </p>

      </div>
    </div>
  );
}
