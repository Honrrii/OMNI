import { useMemo, useState, useEffect } from "react";
import "./styles/omni-design-system.css";
import "./App.css";
import { initSpaceBg } from "./space-bg";
import MissionReportPanel from "./components/MissionReportPanel.jsx";
import MissionGraphReviewPanel from "./components/MissionGraphReviewPanel.jsx";
import CandidateEvaluationPanel from "./components/CandidateEvaluationPanel.jsx";
import MissionIntentPanel from "./components/MissionIntentPanel.jsx";
import PlutoSafetyGatePanel from "./components/PlutoSafetyGatePanel.jsx";
import AeroForgePanel from "./components/AeroForgePanel.jsx";
import VisualBayPanel from "./components/VisualBayPanel.jsx";
import ConceptDossierPanel from "./components/ConceptDossierPanel.jsx";
import HenryEngineLoader from "./components/HenryEngineLoader.jsx";
import OperatorBriefPanel from "./components/OperatorBriefPanel.jsx";
import OmniVisionUploadPanel from "./components/OmniVisionUploadPanel";
import OmniReliabilityPanel from "./components/OmniReliabilityPanel.jsx";

import OmniForgePanel from "./components/OmniForgePanel";
import OmniSimulationPanel from "./components/OmniSimulationPanel";

import omniImg from "./assets/agents/omni.png";
import echoImg from "./assets/agents/echo.png";
import skyImg from "./assets/agents/sky.png";
import korvaImg from "./assets/agents/korva.png";
import isyImg from "./assets/agents/isy.png";
import oliImg from "./assets/agents/oli.png";
import plutoImg from "./assets/agents/pluto.png";
import qazImg from "./assets/agents/qaz.png";
import vegaImg from "./assets/agents/vega.png";

const API_URL = "http://127.0.0.1:8000/api/mission/run";
const EXPORT_API_URL = "http://127.0.0.1:8000/api/mission/export";
const INTERPRET_API_URL = "http://127.0.0.1:8000/api/mission/interpret";
const INTERPRET_AND_RUN_API_URL =
  "http://127.0.0.1:8000/api/mission/interpret-and-run";

const AGENT_IMAGE_MAP = {
  omni: omniImg,
  echo: echoImg,
  vega: vegaImg,
  design: vegaImg,
  sky: skyImg,
  korva: korvaImg,
  isy: isyImg,
  oli: oliImg,
  pluto: plutoImg,
  qaz: qazImg,
};

const JOKE_API_URL =
  "https://v2.jokeapi.dev/joke/Dark,Pun?blacklistFlags=nsfw,religious,political,racist,sexist,explicit&type=single&lang=en";

const MORBID_LOADING_JOKES = [
  "Level 1: I asked my code for stability. It opened a support ticket with my therapist.",
  "Level 2: My deadline smiled at me today. That's how I knew it had teeth.",
  "Level 3: I told my laptop we were in this together. The fan started laughing in binary.",
  "Level 4: I asked life for a sign. It gave me a check engine light and lower back pain.",
  "Level 5: OMNI checked the risk matrix and quietly added my sleep schedule as a known vulnerability.",
  "Level 6: The build failed so dramatically that even the compiler asked for a moment of silence.",
  "Level 7: My ambitions are scalable. Unfortunately, so are the consequences.",
  "Level 8: The robots are not replacing me yet. They're just watching me debug for training data.",
];

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
  { id: "forge", label: "Forge" },
  { id: "simulation", label: "Simulation" },
  { id: "vision", label: "Vision" },
  { id: "blueprint", label: "Blueprint" },
  { id: "agents", label: "Agents" },
  { id: "artifacts", label: "Artifacts" },
  { id: "validation", label: "Validation" },
  { id: "reliability", label: "Reliability" },
  { id: "knowledge", label: "Knowledge" },
  { id: "memory", label: "Memory" },
];

const AGENT_ROLE_MAP = {
  echo: {
    id: "echo",
    name: "Echo",
    role: "Mission Interpreter / Prompt Expansion Agent",
    status: "Idea interpreted",
    figure: "echo",
  },
    vega: {
    id: "design",
    name: "Vega",
    role: "Creative Design, Morphology, and Concept Expansion",
    status: "Design alternatives generated",
    figure: "vega",
  },
    design: {
    id: "design",
    name: "Vega",
    role: "Creative Design, Morphology, and Concept Expansion",
    status: "Design alternatives generated",
    figure: "vega",
    colorName: "Bio-Cyber Teal",
  },
  reed_richards: {
    id: "omni",
    name: "Omni",
    role: "Mission Orchestrator / Systems Intelligence",
    status: "Mission synthesized",
    figure: "omni",
  },
  omni: {
    id: "omni",
    name: "Omni",
    role: "Mission Orchestrator / Systems Intelligence",
    status: "Mission synthesized",
    figure: "omni",
  },
  tony_stark: {
    id: "sky",
    name: "Sky",
    role: "Robotics, ROS2, Drones, and Autonomy",
    status: "Robotics report generated",
    figure: "sky",
  },
  sky: {
    id: "sky",
    name: "Sky",
    role: "Robotics, ROS2, Drones, and Autonomy",
    status: "Robotics report generated",
    figure: "sky",
  },
  shuri: {
    id: "korva",
    name: "Korva",
    role: "Hardware, Electronics, Embedded Systems, and PCB",
    status: "Hardware architecture generated",
    figure: "korva",
  },
  korva: {
    id: "korva",
    name: "Korva",
    role: "Hardware, Electronics, Embedded Systems, and PCB",
    status: "Hardware architecture generated",
    figure: "korva",
  },
  bruce_banner: {
    id: "isy",
    name: "Isy",
    role: "Physics, Controls, Dynamics, and Feasibility",
    status: "Physics analysis generated",
    figure: "isy",
  },
  isy: {
    id: "isy",
    name: "Isy",
    role: "Physics, Controls, Dynamics, and Feasibility",
    status: "Physics analysis generated",
    figure: "isy",
  },
  hank_pym: {
    id: "oli",
    name: "Oli",
    role: "CAD, Fusion 360, 3D Concepts, and Visual Artifacts",
    status: "Design report generated",
    figure: "oli",
  },
  oli: {
    id: "oli",
    name: "Oli",
    role: "CAD, Fusion 360, 3D Concepts, and Visual Artifacts",
    status: "Design report generated",
    figure: "oli",
  },
  ultron: {
    id: "pluto",
    name: "Pluto",
    role: "Risk, Failure Analysis, and Safety Gates",
    status: "Risk critique generated",
    figure: "pluto",
  },
  pluto: {
    id: "pluto",
    name: "Pluto",
    role: "Risk, Failure Analysis, and Safety Gates",
    status: "Risk critique generated",
    figure: "pluto",
  },
  vision: {
    id: "qaz",
    name: "QaZ",
    role: "Validation, Scoring, and Requirements Verification",
    status: "Validation complete",
    figure: "qaz",
  },
  qaz: {
    id: "qaz",
    name: "QaZ",
    role: "Validation, Scoring, and Requirements Verification",
    status: "Validation complete",
    figure: "qaz",
  },
};

const FALLBACK_AGENTS = [
  AGENT_ROLE_MAP.echo,
  AGENT_ROLE_MAP.vega,
  AGENT_ROLE_MAP.omni,
  AGENT_ROLE_MAP.sky,
  AGENT_ROLE_MAP.korva,
  AGENT_ROLE_MAP.isy,
  AGENT_ROLE_MAP.oli,
  AGENT_ROLE_MAP.pluto,
  AGENT_ROLE_MAP.qaz,
];

function getLocalMorbidJoke() {
  const randomIndex = Math.floor(Math.random() * MORBID_LOADING_JOKES.length);
  return MORBID_LOADING_JOKES[randomIndex];
}

async function fetchMorbidLoadingJoke() {
  try {
    const response = await fetch(JOKE_API_URL);

    if (!response.ok) {
      return null;
    }

    const data = await response.json();

    if (data?.error) {
      return null;
    }

    if (data?.type === "single" && data?.joke) {
      return data.joke;
    }

    if (data?.setup && data?.delivery) {
      return `${data.setup} ${data.delivery}`;
    }

    return null;
  } catch (error) {
    console.warn("Could not fetch online loading joke. Using local fallback.", error);
    return null;
  }
}

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

  const PANEL_RENDERED_KEYS = new Set([
    "mission_intent",
    "candidate_evaluation",
    "pluto_safety_gate",
    "aeroforge_intent",
    "aeroforge_entry_gate",
    "visual_bay_manifest",
    "concept_dossier",
    "concept_dossier_manifest",
  ]);

  if (artifacts && typeof artifacts === "object") {
    return Object.entries(artifacts)
      .filter(([key]) => !PANEL_RENDERED_KEYS.has(key))
      .map(([key, value]) => ({
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
    knowledge_context: data.knowledge_context || null,
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

function getRos2Validation(exportResult) {
  return (
    exportResult?.export?.ros2_validation ||
    exportResult?.ros2_validation ||
    null
  );
}

function StatusBadge({ passed, label }) {
  return (
    <span className={`verification-badge ${passed ? "passed" : "failed"}`}>
      {passed ? "✓" : "!"} {label}
    </span>
  );
}

function BuildVerificationCard({ exportResult }) {
  const validation = getRos2Validation(exportResult);

  if (!validation) {
    return null;
  }

  const checks = validation.checks || {};
  const reportPaths = validation.report_paths || {};

  const checkItems = [
    {
      key: "expected_files",
      label: "Expected files",
      passed: checks.expected_files?.passed,
    },
    {
      key: "colcon_build",
      label: "Colcon build",
      passed: checks.colcon_build?.passed,
    },
    {
      key: "installed_files",
      label: "Installed files",
      passed: checks.installed_files?.passed,
    },
    {
      key: "smoke_script",
      label: "Smoke script",
      passed: checks.smoke_script?.passed,
    },
    {
      key: "launch_check",
      label: "Launch check",
      passed: checks.launch_check?.passed,
    },
  ];

  return (
    <div className={`build-verification-card ${validation.passed ? "passed" : "failed"}`}>
      <div className="build-verification-header">
        <div>
          <p className="eyebrow">ROS2 Build Verification</p>
          <h2>{validation.passed ? "Build Verified" : "Build Needs Review"}</h2>
          <p>
            Package: <strong>{validation.package_name || "unknown"}</strong>
          </p>
        </div>

        <div className="verification-score-ring">
          {validation.passed ? "PASS" : "FAIL"}
        </div>
      </div>

      <div className="verification-check-grid">
        {checkItems.map((item) => (
          <StatusBadge
            key={item.key}
            passed={Boolean(item.passed)}
            label={item.label}
          />
        ))}
      </div>

      {checks.launch_check && (
        <div className="verification-details-grid">
          <div>
            <h3>Detected Nodes</h3>
            <ul>
              {(checks.launch_check.nodes || []).map((node, index) => (
                <li key={`${node}-${index}`}>
                  <code>{node}</code>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h3>Detected Topics</h3>
            <ul>
              {(checks.launch_check.topics || []).map((topic, index) => (
                <li key={`${topic}-${index}`}>
                  <code>{topic}</code>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {checks.launch_check?.missing_expected_topics?.length > 0 && (
        <div className="verification-warning">
          <h3>Missing Expected Topics</h3>
          <ul>
            {checks.launch_check.missing_expected_topics.map((topic) => (
              <li key={topic}>
                <code>{topic}</code>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="verification-report-paths">
        <h3>Generated Reports</h3>

        {reportPaths.json_report && (
          <p>
            JSON: <code>{reportPaths.json_report}</code>
          </p>
        )}

        {reportPaths.markdown_report && (
          <p>
            Markdown: <code>{reportPaths.markdown_report}</code>
          </p>
        )}
      </div>
    </div>
  );
}

function AgentFigure({ type = "omni", small = false, hero = false, active = false }) {
  const normalized = String(type || "omni").toLowerCase();
  const size = hero ? "hero" : small ? "small" : "large";
  const imageSrc = AGENT_IMAGE_MAP[normalized] || AGENT_IMAGE_MAP.omni;

  return (
    <div
      className={`agent-portrait-shell ${normalized} ${size} ${
        active ? "active" : ""
      }`}
    >
      <div className="agent-portrait-orbit" />
      <img
        className="agent-portrait-image"
        src={imageSrc}
        alt={`${normalized} agent`}
        draggable="false"
        loading="lazy"
      />
    </div>
  );
}

function CommandAttentionAnimation() {
  return (
    <div className="command-animation-stage" aria-hidden="true">
      <div className="command-grid-floor" />
      <div className="command-scanline" />
      <div className="command-core-pulse">
        <span className="command-core-dot" />
        <span className="command-core-ring ring-one" />
        <span className="command-core-ring ring-two" />
        <span className="command-core-ring ring-three" />
      </div>
      <div className="command-orbit orbit-one" />
      <div className="command-orbit orbit-two" />
      <div className="command-orbit orbit-three" />
      <div className="command-data-rain rain-one" />
      <div className="command-data-rain rain-two" />
      <div className="command-data-rain rain-three" />
    </div>
  );
}

const RAIL_NAV = [
  { id: "command",    label: "Mission"    },
  { id: "blueprint",  label: "Blueprint"  },
  { id: "artifacts",  label: "Artifacts"  },
  { id: "validation", label: "Validation" },
  { id: "simulation", label: "Simulation" },
  { id: "memory",     label: "Memory"     },
];

function getMissionState(missionResult, exportResult, loading, interpreting, exporting) {
  if (loading)      return { label: "EXECUTING",     cls: "hud-executing" };
  if (interpreting) return { label: "ECHO ACTIVE",   cls: "hud-echo"      };
  if (exporting)    return { label: "EXPORTING",     cls: "hud-exporting" };
  const exp = exportResult?.export || {};
  if (exp.graph_review?.status === "reviewed")      return { label: "REVIEW ONLINE", cls: "hud-review" };
  if (exp.ros2_validation?.passed === false)        return { label: "NEEDS REVIEW",  cls: "hud-warn"   };
  if (exportResult)  return { label: "EXPORT READY",  cls: "hud-ok"     };
  if (missionResult) return { label: "MISSION ACTIVE", cls: "hud-active" };
  return { label: "IDLE", cls: "hud-idle" };
}

function SystemTopBar({ activePage, missionResult, exportResult, loading, interpreting, exporting }) {
  const pageLabel = PAGE_ITEMS.find(p => p.id === activePage)?.label || "Command";
  const { label: stateLabel, cls: stateCls } = getMissionState(missionResult, exportResult, loading, interpreting, exporting);

  return (
    <div className="system-top-bar" role="banner" aria-label="OMNI system status">
      <div className="stb-left">
        <span className="stb-brand-dot" aria-hidden="true" />
        <span className="stb-brand">OMNI</span>
        <span className="stb-sep" aria-hidden="true" />
        <span className="stb-system">Command Center</span>
      </div>

      <div className="stb-center">
        <span className="stb-page-label" aria-live="polite">{pageLabel}</span>
      </div>

      <div className="stb-right">
        <span className={`stb-state-chip ${stateCls}`} aria-live="polite" aria-atomic="true">
          <span className="stb-state-dot" aria-hidden="true" />
          {stateLabel}
        </span>
        <span className="stb-link" aria-label="Backend: local link active">
          <span className="stb-link-dot" aria-hidden="true" />
          LOCAL LINK
        </span>
      </div>
    </div>
  );
}

function BottomActionRail({ activePage, setActivePage, missionResult }) {
  return (
    <nav className="bottom-action-rail" aria-label="Quick navigation">
      {RAIL_NAV.map(item => {
        const needsMission = item.id !== "command" && item.id !== "simulation";
        const dimmed = needsMission && !missionResult;
        return (
          <button
            key={item.id}
            className={`bar-btn${activePage === item.id ? " bar-active" : ""}${dimmed ? " bar-dim" : ""}`}
            onClick={() => setActivePage(item.id)}
            aria-current={activePage === item.id ? "page" : undefined}
          >
            <span className="bar-btn-label">{item.label}</span>
          </button>
        );
      })}
    </nav>
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
        <AgentFigure type="echo" small active />
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
        <CommandAttentionAnimation />
        <div className="omni-red-glow" />

        <div className="command-copy">
          <p className="eyebrow">Autonomous Engineering Command</p>
          <h1>OMNI</h1>
          <p className="command-subtitle">
            Give it a mission, or let Echo translate a rough idea into one.
          </p>
        </div>

        <div className="command-signal-strip" aria-hidden="true">
          <span />
          <span />
          <span />
          <span />
          <span />
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

function ForgePage() {
  return (
    <section className="page forge-page-v2">
      <div className="page-header">
        <div>
          <p className="eyebrow">OMNI Forge</p>
          <h1>Workshop Artifact Pipeline</h1>
          <p>
            Convert a workshop prompt into validation data, CAD parameters,
            generated CadQuery scripts, exported STEP/STL files, and a
            human-review artifact manifest.
          </p>
        </div>

        <div className="header-figure-card">
          <AgentFigure type="oli" small active />
          <span>CAD Artifact System</span>
        </div>
      </div>

      <OmniForgePanel />
    </section>
  );
}

function SimulationPage() {
  return (
    <section className="page simulation-page-v2">
      <div className="page-header">
        <div>
          <p className="eyebrow">Simulation</p>
          <h1>ROS2 Mission Control</h1>
          <p>
            Monitor ROS2 nodes, topics, RViz, Gazebo, rosbridge, and Foxglove
            bridge status from the OMNI dashboard. This page is read-only and
            does not control physical robots.
          </p>
        </div>

        <div className="header-figure-card">
          <AgentFigure type="sky" small active />
          <span>ROS2 Status System</span>
        </div>
      </div>

      <OmniSimulationPanel />
    </section>
  );
}

function VisionPage() {
  return (
    <section className="page vision-page-v2">
      <div className="page-header">
        <div>
          <p className="eyebrow">OMNI Vision</p>
          <h1>Image Intake + ML Inference</h1>
          <p>
            Upload images into OMNI&apos;s PyTorch inference service. This demo
            currently uses Fashion-MNIST, but the same pipeline can later
            support CAD screenshots, robot images, component recognition, and
            visual design review.
          </p>
        </div>

        <div className="dual-agent-card">
          <AgentFigure type="vega" small active />
          <AgentFigure type="qaz" small active />
        </div>
      </div>

      <OmniVisionUploadPanel />
    </section>
  );
}

function BlueprintPage({ missionResult, exportResult }) {
  if (!missionResult) {
    return <EmptyPage title="Blueprint" message="Run a mission to generate a blueprint." />;
  }

  return (
    <section className="page blueprint-page-v2">
      <div className="page-header">
        <div>
          <p className="eyebrow">Blueprint</p>
          <h1 className="mission-title">{missionResult.title}</h1>
          {missionResult.createdAt && <p>Created at: {missionResult.createdAt}</p>}
        </div>

        <div className="header-figure-card">
          <AgentFigure type="omni" small active />
          <span>Blueprint Generated</span>
        </div>
      </div>

      {/* ── Operator Brief — quick cockpit summary ── */}
      <OperatorBriefPanel missionResult={missionResult} exportResult={exportResult} />

      {/* ── Full blueprint output — accessible below the brief ── */}
      <details className="ob-details">
        <summary>Full Blueprint Output</summary>
        <div className="blueprint-grid">
          <div className="panel hero-panel">
            <p className="eyebrow">OMNI Synthesis</p>
            <h2>Final Mission Output</h2>
            {missionResult.fullMission && (
              <p className="mission-subtitle-line">{missionResult.fullMission}</p>
            )}
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
      </details>
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
              <AgentFigure
                type={agent.figure}
                small
                active={activeAgent?.id === agent.id}
              />
              <div>
                <h3>{agent.name}</h3>
                <p>{agent.role}</p>
              </div>
            </button>
          ))}
        </div>

        <div className={`agent-detail-panel ${activeAgent.figure}`}>
          <div className="agent-detail-hero">
            <AgentFigure
              key={activeAgent.id}
              type={activeAgent.figure}
              hero
              active
            />
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

  const ros2Validation = getRos2Validation(exportResult);

  return (
    <section className="page artifacts-page-v2">

      {/* ── Compact page header ── */}
      <div className="page-header page-header-compact">
        <div>
          <p className="eyebrow">Generated Files</p>
          <h1>Mission Artifacts</h1>
        </div>

        <div className="export-action-row">
          <button className="primary-button" onClick={exportMission} disabled={exporting}>
            {exporting ? "Exporting + Verifying..." : "Export Mission Files"}
          </button>

          {exportResult && (
            <div className="export-result-card">
              <strong>Export complete</strong>
              <span>{exportResult.export?.file_count || 0} files</span>
              <code>{exportResult.export?.export_dir}</code>
              {ros2Validation && (
                <span className={ros2Validation.passed ? "mini-pass-text" : "mini-fail-text"}>
                  ROS2: {ros2Validation.passed ? "PASSED" : "NEEDS REVIEW"}
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Operator Brief — primary cockpit view ── */}
      <OperatorBriefPanel missionResult={missionResult} exportResult={exportResult} />

      {/* ── Mission artifacts — command-center sectioned layout (Phase 18L) ── */}
      {Array.isArray(missionResult.artifacts) && missionResult.artifacts.length > 0 && (
        <div className="artifact-section-stack">
          {groupArtifactsBySection(missionResult.artifacts).map((section) => (
            <section key={section.id} className="artifact-section-v2">
              <div className="artifact-section-header">
                <div>
                  <h2 className="artifact-section-heading">{section.title}</h2>
                  <p className="artifact-section-description">{section.description}</p>
                </div>
                <span className="artifact-section-count">
                  {section.artifacts.length === 1
                    ? "1 artifact"
                    : `${section.artifacts.length} artifacts`}
                </span>
              </div>
              <div className="artifact-grid-v2">
                {section.artifacts.map((artifact, index) => (
                  <ArtifactCard
                    key={`${section.id}-${artifact.id || artifact.title || "artifact"}-${index}`}
                    title={replaceLegacyNames(artifact.title)}
                    description={replaceLegacyNames(artifact.description)}
                    content={replaceLegacyNames(artifact.content)}
                    id={artifact.id}
                    type={artifact.type}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      {/* ── Deep reports behind collapsible sections ── */}

      <details className="ob-details">
        <summary>Deep Technical Report — Graph Analysis</summary>
        <MissionGraphReviewPanel exportResult={exportResult} />
      </details>

      <MissionIntentPanel exportResult={exportResult} />
      <PlutoSafetyGatePanel exportResult={exportResult} />
      <AeroForgePanel exportResult={exportResult} missionResult={missionResult?.raw} />
      <VisualBayPanel exportResult={exportResult} missionResult={missionResult?.raw} />
      <ConceptDossierPanel exportResult={exportResult} missionResult={missionResult?.raw} />
      <CandidateEvaluationPanel exportResult={exportResult} />

      {ros2Validation && (
        <details className="ob-details">
          <summary>ROS2 Build Verification</summary>
          <BuildVerificationCard exportResult={exportResult} />
        </details>
      )}

      <details className="ob-details">
        <summary>Raw Mission Dossier</summary>
        <MissionReportPanel exportResult={exportResult} />
      </details>

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
          <AgentFigure type="qaz" small active />
          <AgentFigure type="pluto" small active />
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

function KnowledgeContextPage({ missionResult }) {
  if (!missionResult) {
    return (
      <EmptyPage
        title="Knowledge Context"
        message="Run a mission to see which OMNI knowledge domains were used."
      />
    );
  }

  const knowledge = missionResult.knowledge_context;

  if (!knowledge) {
    return (
      <EmptyPage
        title="Knowledge Context"
        message="No local knowledge context was returned for this mission."
      />
    );
  }

  const selectedDomains = knowledge.selected_domains || [];
  const domainSummaries = knowledge.domain_summaries || {};
  const retrievedKnowledge = knowledge.retrieved_knowledge || [];

  return (
    <section className="page knowledge-page-v2">
      <div className="page-header">
        <div>
          <p className="eyebrow">OMNI Local Knowledge</p>
          <h1>Knowledge Context</h1>
          <p>
            Local reference domains and retrieved source chunks OMNI used to ground this mission.
          </p>
        </div>
      </div>

      <div className="knowledge-grid-v2">
        <div className="panel">
          <p className="eyebrow">Selected Domains</p>
          <h2>Knowledge routing</h2>

          <div className="domain-pill-list">
            {selectedDomains.length > 0 ? (
              selectedDomains.map((domain) => (
                <div className="domain-pill" key={domain}>
                  <strong>{domain.replaceAll("_", " ")}</strong>
                  <span>{domainSummaries[domain] || "No summary returned."}</span>
                </div>
              ))
            ) : (
              <p className="muted">No domains selected.</p>
            )}
          </div>
        </div>

        <div className="panel wide-panel">
          <p className="eyebrow">Retrieved Sources</p>
          <h2>Reference chunks</h2>

          <div className="knowledge-hit-list">
            {retrievedKnowledge.length > 0 ? (
              retrievedKnowledge.map((item, index) => (
                <article
                  className="knowledge-hit-card"
                  key={`${item.source_file}-${item.chunk_id}-${index}`}
                >
                  <div className="knowledge-hit-topline">
                    <span>Hit {index + 1}</span>
                    <span>Score {item.score ?? "—"}</span>
                  </div>

                  <h3>{item.source_file || "Unknown source"}</h3>

                  <p className="knowledge-meta">
                    Domain: <strong>{item.domain || "unknown"}</strong> · Chunk:{" "}
                    <strong>{item.chunk_id ?? "unknown"}</strong>
                  </p>

                  {(item.matched_terms || []).length > 0 && (
                    <p className="knowledge-terms">
                      Matched terms: {(item.matched_terms || []).join(", ")}
                    </p>
                  )}

                  <p className="knowledge-excerpt">
                    {item.text || "No excerpt returned."}
                  </p>
                </article>
              ))
            ) : (
              <p className="muted">No retrieved knowledge chunks returned.</p>
            )}
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

        <AgentFigure type="omni" small active />
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

function ReliabilityPage({ missionResult, exportResult }) {
  return (
    <section className="page reliability-page-v2">
      <div className="page-header">
        <div>
          <p className="eyebrow">OMNI Reliability Core</p>
          <h1>Engineering Judgment Dashboard</h1>
          <p>
            Evidence-labeled reliability review for OMNI missions, deterministic
            calculators, ROS2 validation, and OMNITorch visual inspection.
          </p>
        </div>

        <div className="dual-agent-card">
          <AgentFigure type="qaz" small active />
          <AgentFigure type="pluto" small active />
        </div>
      </div>

      <OmniReliabilityPanel
        missionResult={missionResult}
        exportResult={exportResult}
      />
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

// ── Phase 18L: Artifact section grouping ─────────────────────────────────

const ARTIFACT_SECTIONS = [
  {
    id: "mission-overview",
    title: "Mission Overview",
    description: "Top-level mission artifacts: state, summary, intent, and operator brief.",
    keywords: ["mission_state", "mission_summary", "mission_intent", "mission_report", "mission.json", "design_understanding", "operator_brief"],
  },
  {
    id: "design-morphology",
    title: "Design & Morphology",
    description: "Morphology options, component trees, blueprint plans, and hardware architecture.",
    keywords: ["morphology", "component_tree", "blueprint_plan", "hardware_architecture"],
  },
  {
    id: "cad-fusion",
    title: "CAD / Fusion 360",
    description: "Fusion 360 concepts, CAD assembly specs, and 3D design artifacts.",
    keywords: ["fusion", "fusion360", "cad", "assembly_spec"],
  },
  {
    id: "ros2-software",
    title: "ROS2 / Software",
    description: "ROS2 node graphs, package plans, launch configs, and topic contracts.",
    keywords: ["ros2", "node_graph", "package_plan", "launch", "topic_contracts"],
  },
  {
    id: "kicad-electronics",
    title: "KiCad / Electronics",
    description: "KiCad schematics, electronics plans, power budgets, connector maps, and BOMs.",
    keywords: ["kicad", "electronics", "power_budget", "connector_map", "bom"],
  },
  {
    id: "validation-risk",
    title: "Validation / Risk / Safety",
    description: "Risk matrices, safety gates, test checklists, critiques, and readiness reviews.",
    keywords: ["validation", "risk", "safety", "test_checklist", "critique", "revision", "gate", "review", "readiness", "candidate_evaluation"],
  },
  {
    id: "visual-bay",
    title: "Visual Bay",
    description: "Visual previews, render artifacts, and GLTF outputs.",
    keywords: ["visual", "visual_bay", "preview", "gltf", "render"],
  },
  {
    id: "raw-debug",
    title: "Raw / Debug Artifacts",
    description: "Unclassified or debug-level artifacts that did not match a named section.",
    keywords: [],
  },
];

function getArtifactSectionId(artifact = {}) {
  const haystack = String(
    (artifact.id || "") + " " + (artifact.type || "") + " " + (artifact.title || "")
  ).toLowerCase();

  for (const section of ARTIFACT_SECTIONS) {
    if (section.keywords.length === 0) continue;
    if (section.keywords.some((kw) => haystack.includes(kw))) {
      return section.id;
    }
  }

  return "raw-debug";
}

function groupArtifactsBySection(artifacts) {
  const map = new Map(ARTIFACT_SECTIONS.map((s) => [s.id, []]));

  for (const artifact of artifacts) {
    const sid = getArtifactSectionId(artifact);
    map.get(sid).push(artifact);
  }

  return ARTIFACT_SECTIONS.map((section) => ({
    ...section,
    artifacts: map.get(section.id),
  })).filter((section) => section.artifacts.length > 0);
}

// ── Phase 18K: Artifact summarization helpers ─────────────────────────────
function safeJsonParse(str) {
  if (typeof str !== "string") return null;
  try { return JSON.parse(str); } catch { return null; }
}

function safeText(val, fallback) {
  const s = typeof val === "string" ? val.trim() : typeof val === "number" ? String(val) : null;
  return (s && s.length > 0) ? s : (fallback || null);
}

function previewArray(arr, max) {
  if (!Array.isArray(arr) || arr.length === 0) return null;
  const items = arr
    .slice(0, max || 3)
    .map(v => {
      if (typeof v === "string") return v.trim() || null;
      if (v && typeof v === "object") {
        return safeText(v.name || v.id || v.key || v.title || v.test || v.category, null);
      }
      return null;
    })
    .filter(Boolean);
  return items.length > 0 ? items.join(", ") : null;
}

function countKeys(obj) {
  if (Array.isArray(obj)) return obj.length;
  if (obj && typeof obj === "object") return Object.keys(obj).length;
  return 0;
}

function deriveArtifactSummary(id, type, content) {
  const typeKey = ((type || id || "")).toLowerCase().replace(/-/g, "_");
  const data    = safeJsonParse(content);

  function r(label, value) {
    const s = value == null ? null : String(value).trim();
    return (s && s.length > 0) ? { label, value: s } : null;
  }
  function trunc(s, max) {
    if (typeof s !== "string" || !s.trim()) return null;
    const t = s.trim();
    return t.length > (max || 80) ? t.slice(0, (max || 80)) + "…" : t;
  }

  // Mission State — checked before broad "mission" match
  if (typeKey.includes("mission_state") || (typeKey.includes("mission") && typeKey.includes("state"))) {
    if (!data) return { chips: ["mission state"], rows: [] };
    const extra = Object.keys(data).filter(k => !["id","name","status","mission_id","mission_name"].includes(k));
    return {
      chips: ["mission state"],
      rows: [
        r("ID",     safeText(data.mission_id || data.id, null)),
        r("Name",   safeText(data.mission_name || data.name, null)),
        r("Status", safeText(data.status, null)),
        extra.length > 0 ? r("Keys", extra.slice(0, 5).join(", ")) : null,
      ].filter(Boolean),
    };
  }

  // Export Manifest
  if (typeKey.includes("export") || (typeKey.includes("manifest") && !typeKey.includes("concept_dossier"))) {
    if (!data) return { chips: ["export summary"], rows: [] };
    const fileCount = data.file_count ?? (Array.isArray(data.files) ? data.files.length : null);
    const nextCount = Array.isArray(data.files_to_generate_next) ? data.files_to_generate_next.length : null;
    return {
      chips: ["export summary"],
      rows: [
        r("Status",       safeText(data.status, null)),
        fileCount != null ? r("Files", String(fileCount)) : null,
        r("Folder",       safeText(data.folder_name || data.export_dir || data.output_dir, null)),
        nextCount != null ? r("Files pending", String(nextCount)) : null,
      ].filter(Boolean),
    };
  }

  // Mission / Overview (broad)
  if (typeKey === "mission" || typeKey === "overview" || (typeKey.includes("mission") && !typeKey.includes("ros2"))) {
    if (!data) {
      const lines = (content || "").split("\n").filter(Boolean);
      return { chips: ["mission"], rows: [r("Content", trunc(lines[0] || "", 80))].filter(Boolean) };
    }
    return {
      chips: [safeText(data.status, null) || "generated"],
      rows: [
        r("Name",   safeText(data.title || data.name || data.mission_name, null)),
        r("Prompt", trunc(safeText(data.prompt || data.description || data.summary, null), 90)),
      ].filter(Boolean),
    };
  }

  // ROS2 Package Plan
  if (typeKey.includes("ros2_package") || typeKey.includes("ros2_pkg") ||
      (typeKey.includes("ros2") && typeKey.includes("package"))) {
    const nodeCount  = data ? (Array.isArray(data.nodes)  ? data.nodes.length  : countKeys(data.nodes))  : null;
    const topicCount = data ? (Array.isArray(data.topics) ? data.topics.length : countKeys(data.topics)) : null;
    const hasLaunch  = !!(data?.launch_file || data?.launch || data?.launch_config);
    const hasCfg     = !!(data?.config || data?.params || data?.parameters || data?.config_file);
    return {
      chips: ["starter scaffold"],
      rows: [
        r("Package", safeText(data?.package_name || data?.name, null)),
        nodeCount  != null ? r("Nodes",  String(nodeCount))  : null,
        topicCount != null ? r("Topics", String(topicCount)) : null,
        (hasLaunch || hasCfg) ? r("Includes", [hasLaunch ? "launch file" : null, hasCfg ? "config" : null].filter(Boolean).join(", ")) : null,
      ].filter(Boolean),
    };
  }

  // ROS2 Node Graph
  if (typeKey.includes("ros2") && (typeKey.includes("graph") || typeKey.includes("node"))) {
    if (!data) return { chips: ["ros2"], rows: [] };
    // Artifact may be an array of nodes directly, or an object with a nodes field.
    const nodes        = Array.isArray(data) ? data : (Array.isArray(data.nodes) ? data.nodes : []);
    const topics       = Array.isArray(data) ? [] : (Array.isArray(data.topics) ? data.topics : []);
    const nodePreview  = previewArray(nodes, 3);
    const topicPreview = previewArray(topics, 3);
    return {
      chips: [],
      rows: [
        r("Nodes",  `${nodes.length}${nodePreview  ? " — " + nodePreview  : ""}`),
        topics.length > 0 ? r("Topics", `${topics.length}${topicPreview ? " — " + topicPreview : ""}`) : null,
      ].filter(Boolean),
    };
  }

  // Component Tree
  if (typeKey.includes("component") && typeKey.includes("tree")) {
    if (!data) return { chips: ["component tree"], rows: [] };
    const comps       = Array.isArray(data.components) ? data.components : Array.isArray(data.subsystems) ? data.subsystems : [];
    const compPreview = previewArray(comps, 4);
    return {
      chips: ["component tree"],
      rows: [
        r("Components", comps.length > 0 ? String(comps.length) : null),
        compPreview ? r("Names", compPreview) : null,
      ].filter(Boolean),
    };
  }

  // Hardware Architecture
  if (typeKey.includes("hardware") || typeKey.includes("wiring")) {
    if (!data) return { chips: ["hardware summary"], rows: [] };
    const hints = ["sensors","controllers","actuators","power","interfaces","buses","microcontrollers","sbc"]
      .filter(k => data[k] != null)
      .map(k => Array.isArray(data[k]) ? `${k}(${data[k].length})` : k);
    return {
      chips: ["hardware summary"],
      rows: hints.length > 0 ? [r("Sections", hints.slice(0, 5).join(", "))] : [],
    };
  }

  // Fusion360 / CAD Concept
  if (typeKey.includes("fusion") || (typeKey.includes("cad") && typeKey.includes("concept"))) {
    if (!data) return { chips: ["concept CAD only"], rows: [] };
    const comps = Array.isArray(data.components) ? data.components.length : null;
    return {
      chips: ["concept CAD only"],
      rows: [
        r("Concept",    safeText(data.model_name || data.concept_name || data.name || data.title, null)),
        r("Type",       safeText(data.project_type || data.type, null)),
        comps != null ? r("Components", String(comps)) : null,
        data.morphology ? r("Morphology", trunc(safeText(data.morphology, null), 40)) : null,
      ].filter(Boolean),
    };
  }

  // Risk Matrix
  if (typeKey.includes("risk")) {
    if (!data) {
      const lines = (content || "").split("\n").filter(l => l.trim().startsWith("-") || /^\d+\./.test(l));
      return { chips: ["risk summary"], rows: lines.length > 0 ? [r("Items", String(lines.length))] : [] };
    }
    const risks = Array.isArray(data.risks) ? data.risks
                : Array.isArray(data.items) ? data.items
                : Array.isArray(data)       ? data
                : null;
    let riskCount, riskCountLabel = "Risks";
    if (risks) {
      riskCount = risks.length;
    } else {
      // Grouped object like { sky: [...], isy: [...] } — sum nested arrays.
      const objVals = Object.values(data);
      if (objVals.length > 0 && objVals.every(v => Array.isArray(v))) {
        riskCount = objVals.reduce((s, a) => s + a.length, 0);
      } else {
        riskCount = countKeys(data);
        riskCountLabel = "Groups";
      }
    }
    // Only include severity when explicitly present at top level.
    const topSev   = safeText(data.highest_severity || data.max_severity, null);
    const riskPrev = previewArray(risks, 3);
    return {
      chips: ["risk summary"],
      rows: [
        riskCount > 0 ? r(riskCountLabel, String(riskCount)) : null,
        r("Severity", topSev),
        riskPrev ? r("First items", riskPrev) : null,
      ].filter(Boolean),
    };
  }

  // Test Checklist
  if (typeKey.includes("test") || typeKey.includes("checklist") ||
      (typeKey.includes("validation") && typeKey.includes("check"))) {
    if (!data) {
      const lines = (content || "").split("\n").filter(l => /^[-\d[]/.test(l.trim()));
      return { chips: ["checklist"], rows: lines.length > 0 ? [r("Items", String(lines.length))] : [] };
    }
    const checks = Array.isArray(data.tests)     ? data.tests
                 : Array.isArray(data.checklist) ? data.checklist
                 : Array.isArray(data.items)     ? data.items
                 : Array.isArray(data)           ? data
                 : null;
    let checkCount, checkCountLabel = "Checks";
    if (checks) {
      checkCount = checks.length;
    } else {
      // Grouped object — sum nested arrays.
      const objVals = Object.values(data);
      if (objVals.length > 0 && objVals.every(v => Array.isArray(v))) {
        checkCount = objVals.reduce((s, a) => s + a.length, 0);
      } else {
        checkCount = countKeys(data);
        checkCountLabel = "Groups";
      }
    }
    const checkPrev = previewArray(checks, 3);
    return {
      chips: ["checklist"],
      rows: [
        checkCount > 0 ? r(checkCountLabel, String(checkCount)) : null,
        checkPrev ? r("First items", checkPrev) : null,
      ].filter(Boolean),
    };
  }

  // Agent Outputs
  if (typeKey.includes("agent")) {
    if (!data) return { chips: ["agent outputs"], rows: [] };
    const agentList  = Array.isArray(data) ? data : Array.isArray(data.agents) ? data.agents : null;
    if (agentList) {
      const agentPrev = previewArray(agentList, 4);
      return {
        chips: ["agent outputs"],
        rows: [
          r("Agents", String(agentList.length)),
          agentPrev ? r("Names", agentPrev) : null,
        ].filter(Boolean),
      };
    }
    return { chips: ["agent outputs"], rows: [r("Keys", String(countKeys(data)))].filter(Boolean) };
  }

  // Generic fallback
  if (data != null) {
    return {
      chips: [Array.isArray(data) ? "array" : "object"],
      rows: [r("Keys", String(countKeys(data)))].filter(Boolean),
    };
  }
  const lines = (content || "").split("\n").filter(Boolean);
  return { chips: ["text"], rows: [r("Lines", String(lines.length))].filter(Boolean) };
}

function ArtifactCard({ title, description, content, id, type }) {
  const summary    = deriveArtifactSummary(id, type, content);
  const hasSummary = !!(summary && (summary.rows.length > 0 || summary.chips.length > 0));
  return (
    <div className="artifact-card">
      <div className="artifact-header">
        <h3>{title}</h3>
        <span>Generated</span>
      </div>
      <p className="artifact-description">{description}</p>
      {hasSummary && (
        <div className="artifact-summary">
          {summary.chips.length > 0 && (
            <div className="artifact-summary-chips">
              {summary.chips.map((chip, i) => (
                <span key={i} className="artifact-summary-chip">{chip}</span>
              ))}
            </div>
          )}
          {summary.rows.length > 0 && (
            <dl className="artifact-summary-rows">
              {summary.rows.map((row, i) => (
                <div key={i} className="artifact-summary-row">
                  <dt className="artifact-summary-k">{row.label}</dt>
                  <dd className="artifact-summary-v">{row.value}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      )}
      <details className="artifact-raw-details">
        <summary className="artifact-raw-summary">Raw artifact content</summary>
        <div className="artifact-readable">
          <ReportRenderer text={content} />
        </div>
      </details>
    </div>
  );
}

function EmptyPage({ title, message }) {
  return (
    <section className="page empty-page">
      <div className="empty-card">
        <AgentFigure type="omni" hero active />
        <p className="eyebrow">{title}</p>
        <h1>No mission data yet</h1>
        <p>{message}</p>
      </div>
    </section>
  );
}

// LoadingOverlay retained for reference; active loading UI is HenryEngineLoader (Phase 18D).
// eslint-disable-next-line no-unused-vars
function LoadingOverlay({
  message = "OMNI is coordinating the intelligence stack...",
  joke = getLocalMorbidJoke(),
}) {
  return (
    <div className="loading-overlay">
      <div className="loading-card">
        <div className="loading-command-animation" aria-hidden="true">
          <span className="loading-ring ring-a" />
          <span className="loading-ring ring-b" />
          <span className="loading-ring ring-c" />
          <span className="loading-core" />
        </div>
        <p className="eyebrow">Executing Mission</p>
        <h2>{message}</h2>
        <div className="loading-joke-card">
          <p className="eyebrow">Morbid Runtime Humor</p>
          <p>{joke}</p>
        </div>
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
  const [loadingJoke, setLoadingJoke] = useState(getLocalMorbidJoke());

  // ── Space background ──────────────────────────────────────────────
  useEffect(() => {
    return initSpaceBg();
  }, []);

  const pageTitle = useMemo(() => {
    return PAGE_ITEMS.find((page) => page.id === activePage)?.label || "Command";
  }, [activePage]);

  const prepareLoadingJoke = async () => {
    setLoadingJoke(getLocalMorbidJoke());

    const onlineJoke = await fetchMorbidLoadingJoke();

    if (onlineJoke) {
      setLoadingJoke(onlineJoke);
    }
  };

  const launchMission = async () => {
    if (!mission.trim()) {
      setError("Enter a mission before executing OMNI.");
      return;
    }

    setLoading(true);
    prepareLoadingJoke();
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
    prepareLoadingJoke();
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
    <>
      {/* Space background layers — rendered behind everything */}
      <canvas id="space-canvas" />
      <div className="space-grid" />
      <div className="space-scanline" />
      <div className="space-scanline" />
      <div className="space-scanline" />

      <div className="omni-hud-shell">
        <SystemTopBar
          activePage={activePage}
          missionResult={missionResult}
          exportResult={exportResult}
          loading={loading}
          interpreting={interpreting}
          exporting={exporting}
        />

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

          {activePage === "forge" && <ForgePage />}

          {activePage === "simulation" && <SimulationPage />}

          {activePage === "vision" && <VisionPage />}

          {activePage === "blueprint" && <BlueprintPage missionResult={missionResult} exportResult={exportResult} />}

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

          {activePage === "reliability" && (
            <ReliabilityPage
              missionResult={missionResult}
              exportResult={exportResult}
            />
          )}

          {activePage === "knowledge" && (
            <KnowledgeContextPage missionResult={missionResult} />
          )}

          {activePage === "memory" && <MemoryPage missionResult={missionResult} />}
        </section>

        </main>

        <BottomActionRail
          activePage={activePage}
          setActivePage={setActivePage}
          missionResult={missionResult}
        />
      </div>

      {loading && (
        <HenryEngineLoader
          isRunning={loading}
          missionText={commandMode === "idea" ? quickIdea : mission}
          commandMode={commandMode}
          joke={loadingJoke}
        />
      )}
    </>
  );
}

export default App;