import { useMemo, useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000/api/mission/run";
const EXPORT_API_URL = "http://127.0.0.1:8000/api/mission/export";
const INTERPRET_API_URL = "http://127.0.0.1:8000/api/mission/interpret";
const INTERPRET_AND_RUN_API_URL =
  "http://127.0.0.1:8000/api/mission/interpret-and-run";

const DEFAULT_TIMELINE = [
  {
    step: "1",
    title: "Mission Received",
    description: "OMNI accepted the user objective.",
  },
  {
    step: "2",
    title: "Agents Deployed",
    description: "Specialist intelligences were assigned to the mission.",
  },
  {
    step: "3",
    title: "Blueprint Synthesized",
    description: "OMNI combined the system outputs into a usable plan.",
  },
  {
    step: "4",
    title: "Artifacts Generated",
    description: "The final response was organized into mission artifacts.",
  },
];

const PAGE_ITEMS = [
  { id: "command", label: "Command" },
  { id: "blueprint", label: "Blueprint" },
  { id: "agents", label: "Agents" },
  { id: "artifacts", label: "Artifacts" },
  { id: "validation", label: "Validation" },
  { id: "memory", label: "Memory" },
];

const AGENT_ROLE_MAP = {
  echo: {
    id: "echo",
    name: "Echo",
    role: "Mission Interpreter / Prompt Expansion Agent",
    status: "Idea interpreted",
    figure: "echo",
    colorName: "Calm Green",
  },
  reed_richards: {
    id: "omni",
    name: "Omni",
    role: "Mission Orchestrator / Systems Intelligence",
    status: "Mission synthesized",
    figure: "omni",
    colorName: "Red",
  },
  omni: {
    id: "omni",
    name: "Omni",
    role: "Mission Orchestrator / Systems Intelligence",
    status: "Mission synthesized",
    figure: "omni",
    colorName: "Red",
  },
  tony_stark: {
    id: "sky",
    name: "Sky",
    role: "Robotics, ROS2, Drones, and Autonomy",
    status: "Robotics report generated",
    figure: "sky",
    colorName: "Blue",
  },
  sky: {
    id: "sky",
    name: "Sky",
    role: "Robotics, ROS2, Drones, and Autonomy",
    status: "Robotics report generated",
    figure: "sky",
    colorName: "Blue",
  },
  shuri: {
    id: "korva",
    name: "Korva",
    role: "Hardware, Electronics, Embedded Systems, and PCB",
    status: "Hardware architecture generated",
    figure: "korva",
    colorName: "Black / White Outline",
  },
  korva: {
    id: "korva",
    name: "Korva",
    role: "Hardware, Electronics, Embedded Systems, and PCB",
    status: "Hardware architecture generated",
    figure: "korva",
    colorName: "Black / White Outline",
  },
  bruce_banner: {
    id: "isy",
    name: "Isy",
    role: "Physics, Controls, Dynamics, and Feasibility",
    status: "Physics analysis generated",
    figure: "isy",
    colorName: "Sunset Orange",
  },
  isy: {
    id: "isy",
    name: "Isy",
    role: "Physics, Controls, Dynamics, and Feasibility",
    status: "Physics analysis generated",
    figure: "isy",
    colorName: "Sunset Orange",
  },
  hank_pym: {
    id: "oli",
    name: "Oli",
    role: "CAD, Fusion 360, 3D Concepts, and Visual Artifacts",
    status: "Design report generated",
    figure: "oli",
    colorName: "White / Silver",
  },
  oli: {
    id: "oli",
    name: "Oli",
    role: "CAD, Fusion 360, 3D Concepts, and Visual Artifacts",
    status: "Design report generated",
    figure: "oli",
    colorName: "White / Silver",
  },
  ultron: {
    id: "pluto",
    name: "Pluto",
    role: "Risk, Failure Analysis, and Safety Gates",
    status: "Risk critique generated",
    figure: "pluto",
    colorName: "Velvet",
  },
  pluto: {
    id: "pluto",
    name: "Pluto",
    role: "Risk, Failure Analysis, and Safety Gates",
    status: "Risk critique generated",
    figure: "pluto",
    colorName: "Velvet",
  },
  vision: {
    id: "qaz",
    name: "QaZ",
    role: "Validation, Scoring, and Requirements Verification",
    status: "Validation complete",
    figure: "qaz",
    colorName: "Light Pink",
  },
  qaz: {
    id: "qaz",
    name: "QaZ",
    role: "Validation, Scoring, and Requirements Verification",
    status: "Validation complete",
    figure: "qaz",
    colorName: "Light Pink",
  },
};

const FALLBACK_AGENTS = [
  AGENT_ROLE_MAP.echo,
  AGENT_ROLE_MAP.omni,
  AGENT_ROLE_MAP.sky,
  AGENT_ROLE_MAP.korva,
  AGENT_ROLE_MAP.isy,
  AGENT_ROLE_MAP.oli,
  AGENT_ROLE_MAP.pluto,
  AGENT_ROLE_MAP.qaz,
];

function formatTitle(text) {
  if (!text) return "Generated Artifact";

  return String(text)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function replaceLegacyNames(text) {
  if (typeof text !== "string") {
    return text;
  }

  return text
    .replaceAll("Reed Richards", "Omni")
    .replaceAll("Tony Stark", "Sky")
    .replaceAll("Bruce Banner", "Isy")
    .replaceAll("Hank Pym", "Oli")
    .replaceAll("Ultron", "Pluto")
    .replaceAll("Vision", "QaZ")
    .replaceAll("Shuri", "Korva")
    .replaceAll("AI Avengers", "OMNI")
    .replaceAll("Marvel Geniuses HQ", "OMNI Command")
    .replaceAll("Marvel Geniuses", "OMNI")
    .replaceAll(
      "Reed's Final Strategic Recommendation",
      "Omni's Final Strategic Recommendation"
    )
    .replaceAll("READY FOR VISION VALIDATION", "READY FOR QaZ VALIDATION");
}

function createMissionTitle(missionText) {
  const clean = replaceLegacyNames(missionText || "").trim();
  const lower = clean.toLowerCase();

  if (lower.includes("robotic desk assistant")) {
    return "ROS2 Robotic Desk Assistant";
  }

  if (lower.includes("hexacopter")) {
    return "Hexacopter Drone System";
  }

  if (lower.includes("rover")) {
    return "ROS2 Rover Mission";
  }

  if (lower.includes("drone")) {
    return "Drone Mission Blueprint";
  }

  if (lower.includes("fusion 360")) {
    return "Fusion 360 Design Mission";
  }

  if (lower.includes("ros2")) {
    return "ROS2 Robotics Mission";
  }

  if (clean.length > 72) {
    return `${clean.slice(0, 72).trim()}...`;
  }

  return clean || "Mission Blueprint";
}

function cleanMarkdownArtifacts(text) {
  if (typeof text !== "string") return "";

  return replaceLegacyNames(text)
    .replace(/\r/g, "")
    .replace(/```[\s\S]*?```/g, (block) =>
      block
        .replace(/```[a-zA-Z]*\n?/g, "")
        .replace(/```/g, "")
        .trim()
    )
    .replace(/^---+$/gm, "")
    .replace(/^#{1,6}\s*/gm, "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/\*(.*?)\*/g, "$1")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/\\\((.*?)\\\)/g, "$1")
    .replace(/^\s*[-*]\s+/gm, "• ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function stringifyContent(value) {
  if (typeof value === "string") {
    return replaceLegacyNames(value);
  }

  return replaceLegacyNames(JSON.stringify(value, null, 2));
}

function normalizeAgents(agents) {
  if (Array.isArray(agents)) {
    return agents.map((agent, index) => {
      const key = agent.key || agent.id || agent.name?.toLowerCase?.();
      const mapped = AGENT_ROLE_MAP[key];

      return {
        id: mapped?.id || agent.id || `agent-${index}`,
        name: mapped?.name || replaceLegacyNames(agent.name) || "Unknown Agent",
        role: mapped?.role || agent.role || "Specialist Intelligence",
        status: agent.status || mapped?.status || "Report generated",
        figure: mapped?.figure || agent.figure || "omni",
        colorName: mapped?.colorName || agent.colorName || "Unknown",
        report: stringifyContent(agent.report || agent.content || agent.output || ""),
      };
    });
  }

  if (agents && typeof agents === "object") {
    return Object.entries(agents).map(([key, value]) => {
      const mapped = AGENT_ROLE_MAP[key];

      return {
        id: mapped?.id || key,
        name: mapped?.name || formatTitle(key),
        role: mapped?.role || "Specialist Intelligence",
        status: mapped?.status || "Report generated",
        figure: mapped?.figure || key,
        colorName: mapped?.colorName || "Unknown",
        report: stringifyContent(value),
      };
    });
  }

  return FALLBACK_AGENTS.map((agent) => ({
    ...agent,
    report: "",
  }));
}

function normalizeArtifacts(artifacts, mission, finalOutput) {
  if (Array.isArray(artifacts)) {
    return artifacts.map((artifact, index) => ({
      id: artifact.id || `artifact-${index}`,
      title: replaceLegacyNames(artifact.title || "Generated Artifact"),
      description:
        replaceLegacyNames(artifact.description) ||
        "Structured artifact generated by the OMNI mission system.",
      content: stringifyContent(artifact.content || artifact),
      type: artifact.type || "artifact",
    }));
  }

  if (artifacts && typeof artifacts === "object") {
    return Object.entries(artifacts).map(([key, value]) => ({
      id: key,
      title: formatTitle(key),
      description: `Structured ${key.replaceAll(
        "_",
        " "
      )} artifact generated by the OMNI mission system.`,
      content: stringifyContent(value),
      type: key,
    }));
  }

  return [
    {
      id: "mission-overview",
      title: "Mission Overview",
      description: "High-level interpretation of the user mission.",
      content: `Mission: ${mission}`,
      type: "overview",
    },
    {
      id: "engineering-blueprint",
      title: "Engineering Blueprint",
      description: "Synthesized output from the OMNI mission system.",
      content: stringifyContent(finalOutput),
      type: "blueprint",
    },
    {
      id: "next-build-steps",
      title: "Next Build Steps",
      description: "Suggested continuation path for implementation.",
      content:
        "1. Review the generated blueprint.\n" +
        "2. Identify missing assumptions.\n" +
        "3. Convert the strongest sections into artifacts.\n" +
        "4. Move into CAD, ROS2, electronics, or code implementation.\n" +
        "5. Run the mission again with more specific constraints.",
      type: "steps",
    },
    {
      id: "risk-review",
      title: "Risk Review",
      description: "Early feasibility risks to keep the mission grounded.",
      content:
        "Potential risks:\n" +
        "- Missing measurements or constraints.\n" +
        "- Unrealistic hardware assumptions.\n" +
        "- Output may need engineering validation.\n" +
        "- CAD, ROS2, PCB, and simulation plans should be tested separately.",
      type: "risk",
    },
  ];
}

function normalizeMissionResultFromData(data, fallbackMission) {
  const finalOutput =
    data.final_synthesis ||
    data.final_report ||
    data.final_decision ||
    data.response ||
    data.result ||
    data.message ||
    JSON.stringify(data, null, 2);

  const rawMission = replaceLegacyNames(data.mission || fallbackMission || "");

  return {
    title: createMissionTitle(rawMission),
    fullMission: rawMission,
    finalOutput: stringifyContent(finalOutput),
    agents: normalizeAgents(data.agents),
    artifacts: normalizeArtifacts(data.artifacts, rawMission, finalOutput),
    timeline: Array.isArray(data.timeline) ? data.timeline : DEFAULT_TIMELINE,
    createdAt: data.created_at || null,
    validation: data.validation || null,
    raw: data,
  };
}

function getPrimaryReport(missionResult, agentId) {
  if (!missionResult?.agents) return "";

  const target = missionResult.agents.find((agent) => agent.id === agentId);

  return replaceLegacyNames(
    target?.report || "No report has been generated for this intelligence yet."
  );
}

function buildReadableBlocks(text) {
  const cleaned = cleanMarkdownArtifacts(text);

  if (!cleaned) {
    return [{ type: "paragraph", text: "No report content returned yet." }];
  }

  const chunks = cleaned
    .split(/\n{2,}/)
    .map((chunk) => chunk.trim())
    .filter(Boolean);

  return chunks.map((chunk) => {
    const lines = chunk
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);

    const isList = lines.every((line) => /^(\d+\.|•)/.test(line));

    if (isList) {
      return {
        type: "list",
        items: lines.map((line) =>
          line.replace(/^\d+\.\s*/, "").replace(/^•\s*/, "")
        ),
      };
    }

    if (lines.length > 1 && lines[0].length < 90 && !lines[0].endsWith(".")) {
      return {
        type: "section",
        heading: lines[0],
        body: lines.slice(1).join(" "),
      };
    }

    return {
      type: "paragraph",
      text: lines.join(" "),
    };
  });
}

function looksLikeCodeOrJson(text) {
  const value = String(text || "").trim();

  return (
    value.startsWith("{") ||
    value.startsWith("[") ||
    value.includes("│") ||
    value.includes("├──") ||
    value.includes("colcon build") ||
    value.includes("ros2 launch") ||
    value.includes("ros2 topic")
  );
}

function ReportRenderer({ text }) {
  const safeText = replaceLegacyNames(text || "");

  if (looksLikeCodeOrJson(safeText)) {
    return <pre>{safeText}</pre>;
  }

  const blocks = buildReadableBlocks(safeText);

  return (
    <div className="report-content">
      {blocks.map((block, index) => {
        if (block.type === "list") {
          return (
            <ul key={index} className="report-list">
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{item}</li>
              ))}
            </ul>
          );
        }

        if (block.type === "section") {
          return (
            <section key={index} className="report-section">
              <h3 className="report-section-title">{block.heading}</h3>
              <p className="report-paragraph">{block.body}</p>
            </section>
          );
        }

        return (
          <p key={index} className="report-paragraph">
            {block.text}
          </p>
        );
      })}
    </div>
  );
}

function AgentFigure({ type = "omni", small = false }) {
  const shellClass = `figure-shell shape-shell ${type} ${
    small ? "figure-small" : ""
  }`;

  return (
    <div className={shellClass}>
      <div className="shape-aura"></div>

      {type === "echo" && (
        <svg
          className="agent-shape agent-shape-echo"
          viewBox="0 0 180 160"
          role="img"
          aria-label="Echo green soundwave"
        >
          <circle className="echo-source-core" cx="90" cy="80" r="8" />
          <circle className="echo-source-ring" cx="90" cy="80" r="18" />

          <path
            className="echo-wave echo-wave-one left"
            d="M72 58 C52 66 52 94 72 102"
          />
          <path
            className="echo-wave echo-wave-two left"
            d="M58 44 C26 58 26 102 58 116"
          />
          <path
            className="echo-wave echo-wave-three left"
            d="M42 28 C-2 50 -2 110 42 132"
          />

          <path
            className="echo-wave echo-wave-one right"
            d="M108 58 C128 66 128 94 108 102"
          />
          <path
            className="echo-wave echo-wave-two right"
            d="M122 44 C154 58 154 102 122 116"
          />
          <path
            className="echo-wave echo-wave-three right"
            d="M138 28 C182 50 182 110 138 132"
          />

          <line className="echo-center-line" x1="20" y1="80" x2="160" y2="80" />
        </svg>
      )}

      {type === "omni" && (
        <svg
          className="agent-shape agent-shape-omni"
          viewBox="0 0 160 160"
          role="img"
          aria-label="Omni red command core"
        >
          <circle className="shape-outer" cx="80" cy="80" r="54" />
          <circle className="shape-middle" cx="80" cy="80" r="30" />
          <circle className="shape-inner" cx="80" cy="80" r="10" />
          <line className="shape-ray ray-one" x1="80" y1="12" x2="80" y2="34" />
          <line className="shape-ray ray-two" x1="80" y1="126" x2="80" y2="148" />
          <line className="shape-ray ray-three" x1="12" y1="80" x2="34" y2="80" />
          <line className="shape-ray ray-four" x1="126" y1="80" x2="148" y2="80" />
        </svg>
      )}

      {type === "sky" && (
        <svg
          className="agent-shape agent-shape-sky"
          viewBox="0 0 160 160"
          role="img"
          aria-label="Sky blue navigation glyph"
        >
          <polygon className="shape-main" points="80,18 136,132 80,104 24,132" />
          <path className="shape-detail" d="M80 18 L80 104" />
          <path className="shape-detail" d="M48 118 L80 78 L112 118" />
          <circle className="shape-dot dot-one" cx="80" cy="78" r="5" />
        </svg>
      )}

      {type === "isy" && (
        <svg
          className="agent-shape agent-shape-isy"
          viewBox="0 0 160 160"
          role="img"
          aria-label="Isy orange physics orbit"
        >
          <circle className="shape-core" cx="80" cy="80" r="18" />
          <ellipse className="shape-orbit orbit-one" cx="80" cy="80" rx="58" ry="24" />
          <ellipse
            className="shape-orbit orbit-two"
            cx="80"
            cy="80"
            rx="58"
            ry="24"
            transform="rotate(60 80 80)"
          />
          <ellipse
            className="shape-orbit orbit-three"
            cx="80"
            cy="80"
            rx="58"
            ry="24"
            transform="rotate(120 80 80)"
          />
          <circle className="shape-dot particle-one" cx="132" cy="80" r="5" />
        </svg>
      )}

      {type === "oli" && (
        <svg
          className="agent-shape agent-shape-oli"
          viewBox="0 0 160 160"
          role="img"
          aria-label="Oli silver CAD diamond"
        >
          <polygon className="shape-main" points="80,18 136,58 118,132 42,132 24,58" />
          <polygon className="shape-detail-fill" points="80,38 112,62 102,112 58,112 48,62" />
          <path className="shape-detail" d="M24 58 L80 92 L136 58" />
          <path className="shape-detail" d="M80 18 L80 92 L80 142" />
          <circle className="shape-dot dot-one" cx="80" cy="92" r="5" />
        </svg>
      )}

      {type === "pluto" && (
        <svg
          className="agent-shape agent-shape-pluto"
          viewBox="0 0 160 160"
          role="img"
          aria-label="Pluto velvet risk hexagon"
        >
          <polygon className="shape-main" points="80,14 132,44 132,116 80,146 28,116 28,44" />
          <polygon className="shape-inner-polygon" points="80,42 108,58 108,102 80,118 52,102 52,58" />
          <path className="shape-detail" d="M52 58 L108 102" />
          <path className="shape-detail" d="M108 58 L52 102" />
          <circle className="shape-dot dot-one" cx="80" cy="80" r="6" />
        </svg>
      )}

      {type === "qaz" && (
        <svg
          className="agent-shape agent-shape-qaz"
          viewBox="0 0 160 160"
          role="img"
          aria-label="QaZ pink validation prism"
        >
          <polygon className="shape-main" points="80,16 132,80 80,144 28,80" />
          <path className="shape-detail" d="M54 82 L72 100 L110 58" />
          <circle className="shape-ring" cx="80" cy="80" r="48" />
          <circle className="shape-dot dot-one" cx="80" cy="16" r="4" />
          <circle className="shape-dot dot-two" cx="132" cy="80" r="4" />
          <circle className="shape-dot dot-three" cx="80" cy="144" r="4" />
          <circle className="shape-dot dot-four" cx="28" cy="80" r="4" />
        </svg>
      )}

      {type === "korva" && (
        <svg
          className="agent-shape agent-shape-korva"
          viewBox="0 0 160 160"
          role="img"
          aria-label="Korva black hardware module"
        >
          <rect className="shape-main" x="34" y="34" width="92" height="92" rx="14" />
          <rect className="shape-detail-fill" x="56" y="56" width="48" height="48" rx="8" />
          <path className="shape-detail" d="M20 54 H34" />
          <path className="shape-detail" d="M20 80 H34" />
          <path className="shape-detail" d="M20 106 H34" />
          <path className="shape-detail" d="M126 54 H140" />
          <path className="shape-detail" d="M126 80 H140" />
          <path className="shape-detail" d="M126 106 H140" />
          <path className="shape-detail" d="M54 20 V34" />
          <path className="shape-detail" d="M80 20 V34" />
          <path className="shape-detail" d="M106 20 V34" />
          <path className="shape-detail" d="M54 126 V140" />
          <path className="shape-detail" d="M80 126 V140" />
          <path className="shape-detail" d="M106 126 V140" />
          <circle className="shape-dot dot-one" cx="80" cy="80" r="5" />
        </svg>
      )}
    </div>
  );
}

function TopNav({ activePage, setActivePage, missionResult }) {
  return (
    <aside className="omni-sidebar">
      <div className="brand-lockup">
        <div className="brand-mark">◉</div>
        <div>
          <h2>OMNI</h2>
          <p>Engineering Command</p>
        </div>
      </div>

      <nav className="page-nav">
        {PAGE_ITEMS.map((page) => (
          <button
            key={page.id}
            className={`nav-button ${activePage === page.id ? "active" : ""}`}
            onClick={() => setActivePage(page.id)}
          >
            {page.label}
          </button>
        ))}
      </nav>

      <div className="sidebar-status-card">
        <p className="eyebrow">System Status</p>
        <h3>{missionResult ? "Mission Loaded" : "Awaiting Mission"}</h3>
        <p>
          {missionResult
            ? "Blueprint data is ready across all OMNI pages."
            : "Submit a mission from Command to activate the intelligence stack."}
        </p>
      </div>
    </aside>
  );
}

function EchoPreview({ echoResult, setMission }) {
  if (!echoResult) return null;

  return (
    <div className="echo-preview-card">
      <div className="echo-preview-header">
        <AgentFigure type="echo" small />
        <div>
          <p className="eyebrow">Echo Interpretation</p>
          <h2>{echoResult.mission_title || "Interpreted OMNI Mission"}</h2>
        </div>
      </div>

      <h3>Expanded Mission</h3>
      <p>{echoResult.expanded_mission}</p>

      <div className="console-actions echo-preview-actions">
        <button
          className="secondary-button"
          onClick={() => setMission(echoResult.expanded_mission || "")}
        >
          Copy to Full Mission
        </button>
      </div>

      <h3>Detected Domains</h3>
      <div className="echo-chip-row">
        {(echoResult.detected_domains || []).map((domain) => (
          <span key={domain}>{domain}</span>
        ))}
      </div>

      <h3>Missing Inputs</h3>
      <ul>
        {(echoResult.missing_inputs || ["No missing inputs returned."]).map(
          (item, index) => (
            <li key={index}>{item}</li>
          )
        )}
      </ul>

      <h3>Safety Notes</h3>
      <ul>
        {(echoResult.safety_notes || ["No safety notes returned."]).map(
          (item, index) => (
            <li key={index}>{item}</li>
          )
        )}
      </ul>
    </div>
  );
}

function CommandPage({
  mission,
  setMission,
  quickIdea,
  setQuickIdea,
  ideaContext,
  setIdeaContext,
  commandMode,
  setCommandMode,
  interpreting,
  echoResult,
  loading,
  error,
  launchMission,
  interpretIdea,
  interpretAndRun,
  missionResult,
  setActivePage,
}) {
  return (
    <section className="page command-page">
      <div className="command-hero">
        <div className="omni-red-glow"></div>

        <div className="command-copy">
          <p className="eyebrow">Autonomous Engineering Command</p>
          <h1>OMNI</h1>
          <p className="command-subtitle">
            Give it a mission, or let Echo translate a rough idea into one.
          </p>
        </div>

        <div className="command-figure-array">
          <AgentFigure type="echo" small />
          <AgentFigure type="sky" small />
          <AgentFigure type="isy" small />
          <AgentFigure type="omni" />
          <AgentFigure type="oli" small />
          <AgentFigure type="pluto" small />
        </div>

        <div className="mission-console">
          <div className="mode-toggle">
            <button
              className={commandMode === "mission" ? "active" : ""}
              onClick={() => setCommandMode("mission")}
            >
              Full Mission
            </button>

            <button
              className={commandMode === "idea" ? "active" : ""}
              onClick={() => setCommandMode("idea")}
            >
              Quick Idea with Echo
            </button>
          </div>

          {commandMode === "mission" && (
            <>
              <textarea
                value={mission}
                onChange={(event) => setMission(event.target.value)}
                placeholder="Example: Design a ROS2-based robotic desk assistant with a Raspberry Pi, camera module, servo-mounted sensor head, IMU, productivity logging, Fusion 360 enclosure concept, risk matrix, and validation checklist."
              />

              <div className="console-actions">
                <button
                  className="primary-button"
                  onClick={launchMission}
                  disabled={loading}
                >
                  {loading ? "Executing..." : "Execute Mission"}
                </button>

                <button
                  className="secondary-button"
                  onClick={() =>
                    setMission(
                      "Design a ROS2-based robotic desk assistant that uses a Raspberry Pi, camera module, servo-mounted sensor head, IMU, ultrasonic distance sensor, and productivity session logging. Include ROS2 node architecture, hardware wiring plan, Fusion 360 enclosure concept, safety risks, validation checklist, and next artifacts."
                    )
                  }
                >
                  Load Robotics Mission
                </button>

                <button
                  className="secondary-button"
                  onClick={() =>
                    setMission(
                      "Design a 6-motor hexacopter drone with full electrical components, calculated load balance, ROS2 simulation plan, safety review, validation gates, and a Fusion 360 CAD concept."
                    )
                  }
                >
                  Load Drone Mission
                </button>
              </div>
            </>
          )}

          {commandMode === "idea" && (
            <div className="echo-console">
              <textarea
                value={quickIdea}
                onChange={(event) => setQuickIdea(event.target.value)}
                placeholder="Yo Echo, I saw a tiny robot online that follows people around with a camera. I want to build something like that with ROS2 and Fusion 360."
              />

              <textarea
                value={ideaContext}
                onChange={(event) => setIdeaContext(event.target.value)}
                placeholder="Optional context: parts I have, constraints, assignment details, screenshot notes, or what phase I want first."
              />

              <div className="console-actions">
                <button
                  className="secondary-button"
                  onClick={interpretIdea}
                  disabled={interpreting || loading}
                >
                  {interpreting ? "Echo Interpreting..." : "Interpret with Echo"}
                </button>

                <button
                  className="primary-button"
                  onClick={interpretAndRun}
                  disabled={loading || interpreting}
                >
                  {loading ? "Running Echo + OMNI..." : "Interpret + Run + Export"}
                </button>
              </div>

              <EchoPreview echoResult={echoResult} setMission={setMission} />
            </div>
          )}

          {error && <p className="error-message">{error}</p>}
        </div>

        {missionResult && (
          <button className="jump-button" onClick={() => setActivePage("blueprint")}>
            Open Latest Blueprint →
          </button>
        )}
      </div>
    </section>
  );
}

function BlueprintPage({ missionResult }) {
  if (!missionResult) {
    return <EmptyPage title="Blueprint" message="Run a mission to generate a blueprint." />;
  }

  return (
    <section className="page blueprint-page-v2">
      <div className="page-header">
        <div>
          <p className="eyebrow">Blueprint</p>
          <h1 className="mission-title">{missionResult.title}</h1>
          {missionResult.fullMission && (
            <p className="mission-subtitle-line">{missionResult.fullMission}</p>
          )}
          {missionResult.createdAt && <p>Created at: {missionResult.createdAt}</p>}
        </div>

        <div className="header-figure-card">
          <AgentFigure type="omni" small />
          <span>Blueprint Generated</span>
        </div>
      </div>

      <div className="blueprint-grid">
        <div className="panel hero-panel">
          <p className="eyebrow">OMNI Synthesis</p>
          <h2>Final Mission Output</h2>
          <div className="soft-report blueprint-report">
            <ReportRenderer text={missionResult.finalOutput} />
          </div>
        </div>

        <div className="panel">
          <p className="eyebrow">Timeline</p>
          <h2>Mission Flow</h2>
          <div className="timeline">
            {missionResult.timeline.map((item) => (
              <TimelineItem
                key={item.step}
                step={item.step}
                title={item.title || item.event}
                description={replaceLegacyNames(item.description)}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function AgentsPage({ missionResult }) {
  const agents = missionResult?.agents || FALLBACK_AGENTS;
  const [activeAgentId, setActiveAgentId] = useState(agents[0]?.id || "echo");

  const activeAgent =
    agents.find((agent) => agent.id === activeAgentId) || agents[0] || FALLBACK_AGENTS[0];

  const activeReport = missionResult
    ? getPrimaryReport(missionResult, activeAgent.id)
    : "Run a mission to populate this agent report.";

  return (
    <section className="page agents-page-v2">
      <div className="page-header">
        <div>
          <p className="eyebrow">Agent Stack</p>
          <h1>Specialist Intelligences</h1>
          <p>
            Each intelligence owns a focused part of the mission and contributes
            to the final OMNI blueprint.
          </p>
        </div>
      </div>

      <div className="agent-tab-layout">
        <div className="agent-tabs">
          {agents.map((agent) => (
            <button
              key={agent.id}
              className={`agent-tab ${agent.figure} ${
                activeAgent?.id === agent.id ? "active" : ""
              }`}
              onClick={() => setActiveAgentId(agent.id)}
            >
              <AgentFigure type={agent.figure} small />
              <div>
                <h3>{agent.name}</h3>
                <p>{agent.role}</p>
              </div>
            </button>
          ))}
        </div>

        <div className={`agent-detail-panel ${activeAgent.figure}`}>
          <div className="agent-detail-hero">
            <AgentFigure type={activeAgent.figure} />
            <div>
              <p className="eyebrow">{activeAgent.colorName}</p>
              <h2>{activeAgent.name}</h2>
              <p>{activeAgent.role}</p>
              <span className="status-pill">{activeAgent.status || "Ready"}</span>
            </div>
          </div>

          <div className="agent-report">
            <p className="eyebrow">Agent Report</p>
            <div className="soft-report">
              <ReportRenderer text={activeReport} />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function ArtifactsPage({ missionResult, exportMission, exporting, exportResult }) {
  if (!missionResult) {
    return <EmptyPage title="Artifacts" message="Run a mission to generate artifacts." />;
  }

  return (
    <section className="page artifacts-page-v2">
      <div className="page-header">
        <div>
          <p className="eyebrow">Generated Files</p>
          <h1>Mission Artifacts</h1>
          <p>
            Structured outputs from OMNI. These are the pieces that can later become
            diagrams, files, tables, code, or CAD prompts.
          </p>

          <div className="export-action-row">
            <button className="primary-button" onClick={exportMission} disabled={exporting}>
              {exporting ? "Exporting..." : "Export Mission Files"}
            </button>

            {exportResult && (
              <div className="export-result-card">
                <strong>Export complete</strong>
                <span>{exportResult.export?.file_count || 0} files generated</span>
                <code>{exportResult.export?.export_dir}</code>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="artifact-grid-v2">
        {missionResult.artifacts.map((artifact) => (
          <ArtifactCard
            key={artifact.id || artifact.title}
            title={replaceLegacyNames(artifact.title)}
            description={replaceLegacyNames(artifact.description)}
            content={replaceLegacyNames(artifact.content)}
          />
        ))}
      </div>
    </section>
  );
}

function ValidationPage({ missionResult }) {
  if (!missionResult) {
    return <EmptyPage title="Validation" message="Run a mission to generate validation data." />;
  }

  const validation = missionResult.validation;

  return (
    <section className="page validation-page-v2">
      <div className="page-header">
        <div>
          <p className="eyebrow">Validation</p>
          <h1>QaZ + Pluto Review</h1>
          <p>
            Validation, missing evidence, safety gates, and required next tests
            are separated here so the system stays grounded.
          </p>
        </div>

        <div className="dual-agent-card">
          <AgentFigure type="qaz" small />
          <AgentFigure type="pluto" small />
        </div>
      </div>

      <div className="validation-grid">
        <div className="panel validation-score-panel">
          <p className="eyebrow">QaZ Verdict</p>
          <h2>{validation?.verdict || "No verdict returned"}</h2>
          <p className="score-display">
            {validation?.score ? `${Number(validation.score).toFixed(2)} / 10` : "No score"}
          </p>
        </div>

        <div className="panel">
          <p className="eyebrow">Missing Evidence</p>
          <h2>What still needs proof?</h2>
          <ul className="clean-list">
            {(validation?.missing_evidence || ["No missing evidence returned."]).map(
              (item, index) => (
                <li key={index}>{replaceLegacyNames(item)}</li>
              )
            )}
          </ul>
        </div>

        <div className="panel wide-panel">
          <p className="eyebrow">Required Next Tests</p>
          <h2>Next validation gates</h2>
          <ul className="clean-list">
            {(validation?.required_next_tests || [
              "No required next tests returned.",
            ]).map((item, index) => (
              <li key={index}>{replaceLegacyNames(item)}</li>
            ))}
          </ul>
        </div>

        <div className="panel wide-panel">
          <p className="eyebrow">Validation Report</p>
          <h2>Full QaZ Report</h2>
          <div className="soft-report">
            <ReportRenderer text={validation?.report || "No validation report returned."} />
          </div>
        </div>
      </div>
    </section>
  );
}

function MemoryPage({ missionResult }) {
  return (
    <section className="page memory-page-v2">
      <div className="page-header">
        <div>
          <p className="eyebrow">Memory</p>
          <h1>Mission History</h1>
          <p>
            This page is reserved for the next upgrade: saved missions, feedback,
            scores, reusable artifacts, and what OMNI should remember.
          </p>
        </div>

        <AgentFigure type="omni" small />
      </div>

      <div className="memory-grid">
        <div className="panel">
          <p className="eyebrow">Current Status</p>
          <h2>{missionResult ? "Latest mission loaded" : "No active mission yet"}</h2>
          <p>
            {missionResult
              ? "The latest mission is available across the Blueprint, Agents, Artifacts, and Validation pages."
              : "Run a mission from Command to begin building the mission history workflow."}
          </p>
        </div>

        <div className="panel">
          <p className="eyebrow">Planned Upgrade</p>
          <h2>OMNI Memory Core</h2>
          <p>
            Future versions can store mission summaries, user feedback, ratings,
            accepted artifacts, rejected outputs, and preferred engineering style.
          </p>
        </div>
      </div>
    </section>
  );
}

function TimelineItem({ step, title, description }) {
  return (
    <div className="timeline-item">
      <div className="timeline-dot">{step}</div>
      <div>
        <h4>{title}</h4>
        <p>{description}</p>
      </div>
    </div>
  );
}

function ArtifactCard({ title, description, content }) {
  return (
    <div className="artifact-card">
      <div className="artifact-header">
        <h3>{title}</h3>
        <span>Generated</span>
      </div>
      <p className="artifact-description">{description}</p>
      <div className="artifact-readable">
        <ReportRenderer text={content} />
      </div>
    </div>
  );
}

function EmptyPage({ title, message }) {
  return (
    <section className="page empty-page">
      <div className="empty-card">
        <AgentFigure type="omni" />
        <p className="eyebrow">{title}</p>
        <h1>No mission data yet</h1>
        <p>{message}</p>
      </div>
    </section>
  );
}

function LoadingOverlay({ message = "OMNI is coordinating the intelligence stack..." }) {
  return (
    <div className="loading-overlay">
      <div className="loading-card">
        <AgentFigure type="omni" />
        <p className="eyebrow">Executing Mission</p>
        <h2>{message}</h2>
      </div>
    </div>
  );
}

function App() {
  const [activePage, setActivePage] = useState("command");

  const [commandMode, setCommandMode] = useState("mission");
  const [mission, setMission] = useState("");
  const [quickIdea, setQuickIdea] = useState("");
  const [ideaContext, setIdeaContext] = useState("");
  const [echoResult, setEchoResult] = useState(null);

  const [loading, setLoading] = useState(false);
  const [interpreting, setInterpreting] = useState(false);
  const [exporting, setExporting] = useState(false);

  const [exportResult, setExportResult] = useState(null);
  const [missionResult, setMissionResult] = useState(null);
  const [error, setError] = useState("");

  const pageTitle = useMemo(() => {
    return PAGE_ITEMS.find((page) => page.id === activePage)?.label || "Command";
  }, [activePage]);

  const launchMission = async () => {
    if (!mission.trim()) {
      setError("Enter a mission before executing OMNI.");
      return;
    }

    setLoading(true);
    setError("");
    setExportResult(null);
    setMissionResult(null);

    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          mission: mission.trim(),
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || "Backend mission request failed.");
      }

      const data = await response.json();
      const normalizedResult = normalizeMissionResultFromData(data, mission.trim());

      setMissionResult(normalizedResult);
      setActivePage("blueprint");
    } catch (err) {
      console.error(err);
      setError(
        "The mission could not execute. Make sure your FastAPI backend is running on http://127.0.0.1:8000 and that /api/mission/run is available."
      );
    } finally {
      setLoading(false);
    }
  };

  const interpretIdea = async () => {
    if (!quickIdea.trim()) {
      setError("Enter a quick idea for Echo to interpret.");
      return;
    }

    setInterpreting(true);
    setError("");
    setEchoResult(null);

    try {
      const response = await fetch(INTERPRET_API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          idea: quickIdea.trim(),
          context: ideaContext.trim(),
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || "Echo interpretation failed.");
      }

      const data = await response.json();
      const interpretation = data.interpretation || null;

      setEchoResult(interpretation);

      if (interpretation?.expanded_mission) {
        setMission(interpretation.expanded_mission);
      }
    } catch (err) {
      console.error(err);
      setError("Echo could not interpret the idea. Check that the backend is running.");
    } finally {
      setInterpreting(false);
    }
  };

  const interpretAndRun = async () => {
    if (!quickIdea.trim()) {
      setError("Enter a quick idea before running Echo + OMNI.");
      return;
    }

    setLoading(true);
    setError("");
    setExportResult(null);
    setMissionResult(null);

    try {
      const response = await fetch(INTERPRET_AND_RUN_API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          idea: quickIdea.trim(),
          context: ideaContext.trim(),
          auto_export: true,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || "Echo + OMNI request failed.");
      }

      const data = await response.json();
      const missionData = data.mission_result;

      if (!missionData) {
        throw new Error("No mission_result returned from interpret-and-run.");
      }

      const normalizedResult = normalizeMissionResultFromData(
        missionData,
        missionData.mission || quickIdea.trim()
      );

      setEchoResult(data.interpretation || null);
      setExportResult(data.export ? { export: data.export } : null);
      setMissionResult(normalizedResult);
      setActivePage("blueprint");
    } catch (err) {
      console.error(err);
      setError("Echo could not interpret and run the mission. Check your backend.");
    } finally {
      setLoading(false);
    }
  };

  const exportMission = async () => {
    if (!missionResult?.raw) {
      setError("Run a mission before exporting files.");
      return;
    }

    setExporting(true);
    setError("");
    setExportResult(null);

    try {
      const response = await fetch(EXPORT_API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          mission_result: missionResult.raw,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || "Mission export request failed.");
      }

      const data = await response.json();
      setExportResult(data);
    } catch (err) {
      console.error(err);
      setError(
        "The mission could not export. Make sure /api/mission/export is available and the backend is running."
      );
    } finally {
      setExporting(false);
    }
  };

  return (
    <main className="omni-app-shell">
      <TopNav
        activePage={activePage}
        setActivePage={setActivePage}
        missionResult={missionResult}
      />

      <section className="omni-main">
        <header className="mobile-topbar">
          <div>
            <p className="eyebrow">OMNI</p>
            <h2>{pageTitle}</h2>
          </div>
        </header>

        {activePage === "command" && (
          <CommandPage
            mission={mission}
            setMission={setMission}
            quickIdea={quickIdea}
            setQuickIdea={setQuickIdea}
            ideaContext={ideaContext}
            setIdeaContext={setIdeaContext}
            commandMode={commandMode}
            setCommandMode={setCommandMode}
            interpreting={interpreting}
            echoResult={echoResult}
            loading={loading}
            error={error}
            launchMission={launchMission}
            interpretIdea={interpretIdea}
            interpretAndRun={interpretAndRun}
            missionResult={missionResult}
            setActivePage={setActivePage}
          />
        )}

        {activePage === "blueprint" && <BlueprintPage missionResult={missionResult} />}

        {activePage === "agents" && <AgentsPage missionResult={missionResult} />}

        {activePage === "artifacts" && (
          <ArtifactsPage
            missionResult={missionResult}
            exportMission={exportMission}
            exporting={exporting}
            exportResult={exportResult}
          />
        )}

        {activePage === "validation" && <ValidationPage missionResult={missionResult} />}

        {activePage === "memory" && <MemoryPage missionResult={missionResult} />}
      </section>

      {loading && (
        <LoadingOverlay
          message={
            commandMode === "idea"
              ? "Echo is interpreting, OMNI is assembling, and exports are being prepared..."
              : "OMNI is coordinating the intelligence stack..."
          }
        />
      )}
    </main>
  );
}

export default App;