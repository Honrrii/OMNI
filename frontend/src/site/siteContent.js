// Copy for the public OMNI overview. Every statement here should stay true to
// the repository: agents/*.py, backend/app/**, omni/**, and
// docs/OMNI_FORGE_ROADMAP.md. Update the copy when those change.

import { OMNI_CORE, SPECIALIST_AGENTS } from "../content/agents.js";

export const LINKS = {
  console: "#/console",
  repository: "https://github.com/Honrrii/OMNI",
};

export const NAV_ITEMS = [
  { href: "#about", label: "About" },
  { href: "#capabilities", label: "Capabilities" },
  { href: "#agents", label: "Agents" },
  { href: "#system", label: "System" },
  { href: "#roadmap", label: "Roadmap" },
];

export const HERO = {
  eyebrow: "Experimental · Local-first",
  title: "OMNI",
  expandedName: "Orchestrated Multi-AI Networked Intelligence",
  lede: "An AI-native engineering system that turns a rough idea into a structured, reviewable engineering package.",
  support:
    "OMNI coordinates specialist agents, deterministic engineering checks, and real toolchains — ROS 2, CadQuery, Fusion 360, and KiCad — so every mission ends in artifacts you can inspect and build from.",
  facts: [
    { term: "Agents", detail: "Eight specialists in one ordered pipeline" },
    { term: "Checks", detail: "Deterministic gates and calculators" },
    { term: "Runtime", detail: "Local FastAPI backend and React console" },
    { term: "Authority", detail: "Human approval for physical action" },
  ],
};

export const ABOUT = {
  eyebrow: "What OMNI is",
  title: "Not a chatbot. A coordinated engineering system.",
  paragraphs: [
    "Hardware projects cross many disciplines at once: software, robotics, mechanical design, electronics, physics, and testing. OMNI is built to hold them together in one structured workflow.",
    "A mission enters as plain language. OMNI interprets it, routes it through specialist agents with defined responsibilities, checks the results with deterministic gates, and exports everything as a mission dossier you can inspect, question, and build from.",
  ],
  facts: [
    { term: "Input", detail: "A rough idea or a complete mission brief" },
    {
      term: "Output",
      detail: "ROS 2 packages, CAD scripts, engineering reports, and a provenance record",
    },
    { term: "Boundary", detail: "Supports engineering judgment. Never replaces it." },
  ],
};

export const CAPABILITY_STATUS = {
  available: { label: "Available", definition: "Implemented and used in missions today" },
  early: { label: "Early", definition: "A working foundation with limited scope" },
  experimental: { label: "Experimental", definition: "Functional, demonstration-grade" },
  research: { label: "Research", definition: "Exploratory work outside the mission pipeline" },
};

export const CAPABILITIES_SECTION = {
  eyebrow: "Capabilities",
  title: "What OMNI does today, and what is still emerging.",
  intro:
    "Each capability is labeled by maturity, so it is clear what is dependable now and what is still being built.",
  items: [
    {
      title: "Mission interpretation",
      status: "available",
      summary:
        "Echo expands a rough idea into a structured mission with detected domains, missing inputs, and safety notes. Intent extraction and the mission graph are deterministic.",
    },
    {
      title: "Engineering design",
      status: "available",
      summary:
        "Vega proposes distinct design alternatives, and a deterministic evaluator scores each candidate from every specialist's perspective.",
    },
    {
      title: "Robotics and ROS 2",
      status: "available",
      summary:
        "Generates ROS 2 Python packages — nodes, topics, launch files, and configuration — then checks them with colcon build and smoke tests when ROS 2 is installed.",
    },
    {
      title: "CAD and geometry",
      status: "available",
      summary:
        "Plans parametric parts, generates CadQuery and Fusion 360 scripts, exports STEP and STL, and previews 3D assets in the browser.",
    },
    {
      title: "Electronics and hardware",
      status: "early",
      summary:
        "Starter electronics plans and KiCad project scaffolding, checked against a KiCad knowledge gate.",
    },
    {
      title: "Physics reasoning",
      status: "available",
      summary:
        "Isy reviews dynamics, controls, loads, and sensor fusion, backed by deterministic engineering calculators.",
    },
    {
      title: "Validation and critique",
      status: "available",
      summary:
        "Reliability gates report PASS, WARN, FAIL, or BLOCKED, while Pluto and QaZ flag risk and missing evidence. Gates are advisory aids, not certification.",
    },
    {
      title: "Simulation",
      status: "early",
      summary:
        "Simulation planning within missions, plus read-only monitoring of ROS 2 nodes, topics, RViz, Gazebo, and Foxglove bridges.",
    },
    {
      title: "Machine learning",
      status: "experimental",
      summary:
        "OMNITorch wraps PyTorch models behind a stable inference API. Today it serves a demonstration image classifier.",
    },
    {
      title: "Software evolution",
      status: "research",
      summary:
        "TestCube and Super-Build explore evidence-first, human-gated code change: isolated candidate patches, deterministic arbitration, and independent review.",
    },
  ],
};

export const AGENTS_SECTION = {
  eyebrow: "Agents",
  title: "Eight specialists. One accountable pipeline.",
  intro:
    "Each agent owns a defined slice of the engineering problem and returns structured output the next stage can check.",
  core: OMNI_CORE,
  agents: SPECIALIST_AGENTS,
};

export const SYSTEM = {
  eyebrow: "System",
  title: "A structured pipeline, not a single prompt.",
  intro:
    "Every mission moves through the same ordered stages. Model reasoning is paired with deterministic checks, and every stage leaves a record.",
  stages: [
    { step: "01", name: "Interpret", owner: "Echo", detail: "Idea to structured mission" },
    { step: "02", name: "Strategize", owner: "OMNI Core", detail: "Mission strategy and routing" },
    {
      step: "03",
      name: "Design",
      owner: "Vega · Sky · Korva · Isy · Oli",
      detail: "Specialist engineering reports",
    },
    { step: "04", name: "Critique", owner: "Pluto · OMNI Core", detail: "Risk review and revised blueprint" },
    { step: "05", name: "Validate", owner: "QaZ", detail: "Scoring and missing evidence" },
    { step: "06", name: "Export", owner: "Deterministic gates", detail: "Build checks, reliability, provenance" },
  ],
  outcome: { name: "Human review", detail: "You decide what gets built." },
  principles: [
    {
      title: "Structured by design",
      detail:
        "Every agent has a defined responsibility and output schema. Reports are parsed and carried forward, not just displayed.",
    },
    {
      title: "Deterministic where it counts",
      detail:
        "Intent extraction, mission graph validation, reliability calculators, and gates run as plain, tested code with no model in the loop.",
    },
    {
      title: "Provenance, not just output",
      detail:
        "Each export records what was generated, which assumptions were made, and what still needs validation.",
    },
    {
      title: "Human-gated",
      detail:
        "OMNI may generate, validate, and prepare. Fabrication, hardware control, and irreversible actions stay behind explicit human approval.",
    },
  ],
  footnote:
    "Runs locally as a modular monolith: one FastAPI backend, one React console, one in-process supervisor.",
};

export const ROADMAP = {
  eyebrow: "Roadmap",
  title: "Accountability before autonomy.",
  intro:
    "OMNI grows deliberately. Each new capability arrives with the checks, records, and human gates that make it trustworthy.",
  horizons: [
    {
      label: "Now",
      title: "Engineering foundation",
      items: [
        "Mission interpretation and multi-agent synthesis",
        "ROS 2 package generation with build validation",
        "CadQuery STEP and STL export",
        "Reliability gates and provenance-backed mission dossiers",
      ],
    },
    {
      label: "Next",
      title: "Closing the design loop",
      items: [
        "A dedicated simulation core, beyond planning and status",
        "Broader design-space exploration and candidate evaluation",
        "Fabrication preparation: slicer guidance, print orientation, G-code plans",
      ],
    },
    {
      label: "Later",
      title: "Wider engineering reach",
      items: [
        "Deeper electronics, mechanical, and aerospace workflows",
        "Workshop integration, with human approval for every physical action",
        "Evidence-first software evolution through Super-Build",
      ],
    },
  ],
  motto: "No mission dies as output. Every mission becomes provenance.",
};

export const DEMOS = {
  eyebrow: "Demonstrations",
  title: "Walkthroughs are on the way.",
  intro:
    "Recorded missions, generated artifacts, and console captures will be published here as OMNI matures.",
  placeholders: ["Mission walkthrough", "CAD export", "Validation dossier"],
};

export const FOOTER = {
  note: "OMNI is experimental software. Its outputs support qualified engineering review and never replace it.",
};
