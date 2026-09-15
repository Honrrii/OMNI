// Canonical OMNI agent roster, shared by the public overview and the mission
// console. Names and responsibilities mirror the implementations in agents/*.py
// and the supervisor in agents/supervisor.py.

export const OMNI_CORE = {
  id: "omni",
  name: "OMNI Core",
  role: "Orchestration and synthesis",
  summary:
    "Sets mission strategy, routes work to the specialists, and synthesizes the final blueprint.",
};

export const SPECIALIST_AGENTS = [
  {
    id: "echo",
    name: "Echo",
    role: "Mission interpretation",
    summary:
      "Turns a rough idea into a structured mission brief and flags missing inputs before work begins.",
  },
  {
    id: "vega",
    name: "Vega",
    role: "Conceptual design",
    summary:
      "Explores distinct, physically plausible design alternatives and morphology options.",
  },
  {
    id: "sky",
    name: "Sky",
    role: "Robotics and autonomy",
    summary:
      "Defines ROS 2 architecture: nodes, topics, launch plans, and autonomy workflow.",
  },
  {
    id: "korva",
    name: "Korva",
    role: "Electronics and hardware",
    summary:
      "Shapes hardware architecture, wiring, power assumptions, and embedded constraints.",
  },
  {
    id: "isy",
    name: "Isy",
    role: "Physics reasoning",
    summary:
      "Tests feasibility across dynamics, controls, mass, torque, stability, and sensor fusion.",
  },
  {
    id: "oli",
    name: "Oli",
    role: "CAD and geometry",
    summary:
      "Develops CAD concepts, component layout, and Fusion 360 modeling steps.",
  },
  {
    id: "pluto",
    name: "Pluto",
    role: "Critique and risk review",
    summary:
      "Surfaces unsafe assumptions, failure modes, and missing requirements, and drives revision.",
  },
  {
    id: "qaz",
    name: "QaZ",
    role: "Validation and verification",
    summary:
      "Scores mission output against requirements and names the evidence still required.",
  },
];

export const AGENT_PROFILES = Object.fromEntries(
  [OMNI_CORE, ...SPECIALIST_AGENTS].map((agent) => [agent.id, agent])
);
