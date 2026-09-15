import SnailMark from "./SnailMark.jsx";

const GROUPS = [
  {
    label: "Mission",
    pages: [
      ["command", "Command"],
      ["blueprint", "Blueprint"],
      ["agents", "Agents"],
    ],
  },
  {
    label: "Engineering",
    pages: [
      ["design", "Design"],
      ["robotics", "Robotics"],
      ["forge", "CAD · Forge"],
      ["electronics", "Electronics"],
      ["simulation", "Simulation"],
      ["vision", "OMNITorch"],
    ],
  },
  {
    label: "Evidence",
    pages: [
      ["artifacts", "Artifacts · Visual Bay"],
      ["validation", "Validation & critique"],
      ["reliability", "Reliability"],
      ["knowledge", "Knowledge"],
      ["memory", "Memory"],
    ],
  },
];
// Shared route metadata; legacy route IDs remain valid.
// eslint-disable-next-line react-refresh/only-export-components
export const PAGE_ITEMS = GROUPS.flatMap((group) =>
  group.pages.map(([id, label]) => ({ id, label })),
);

export function SystemTopBar({ activePage, missionResult }) {
  return (
    <header className="system-top-bar">
      <div className="stb-left">
        <a className="stb-brand" href="#/">
          OMNI
        </a>
        <span className="stb-sep" aria-hidden="true" />
        <span className="stb-system">Engineering laboratory</span>
      </div>
      <div className="workspace-context">
        <span>{missionResult ? "Active mission" : "Workspace"}</span>
        <strong title={missionResult?.title}>
          {missionResult?.title || "Start with a mission. Build with evidence."}
        </strong>
      </div>
      <span className="stb-page-label">
        {PAGE_ITEMS.find((p) => p.id === activePage)?.label}
      </span>
    </header>
  );
}

export function TopNav({ activePage, setActivePage }) {
  return (
    <aside className="omni-sidebar">
      <a className="brand-lockup" href="#/" title="OMNI overview">
        <SnailMark size={44} className="brand-mark" decorative />
        <div>
          <h2>OMNI</h2>
          <p>Mission console</p>
        </div>
      </a>
      <nav className="workspace-nav" aria-label="Workspaces">
        {GROUPS.map((group) => (
          <div className="nav-group" key={group.label}>
            <p className="eyebrow">{group.label}</p>
            {group.pages.map(([id, label]) => (
              <button
                key={id}
                className={`nav-button ${activePage === id ? "active" : ""}`}
                aria-current={activePage === id ? "page" : undefined}
                onClick={() => setActivePage(id)}
              >
                {label}
              </button>
            ))}
          </div>
        ))}
      </nav>
      <a className="sidebar-overview" href="#/">
        ← Laboratory overview
      </a>
    </aside>
  );
}

export function BottomActionRail({ activePage, setActivePage }) {
  return (
    <nav className="bottom-action-rail" aria-label="Quick navigation">
      {[
        ["command", "Mission"],
        ["artifacts", "Artifacts"],
        ["validation", "Validation"],
        ["vision", "OMNITorch"],
      ].map(([id, label]) => (
        <button
          key={id}
          className={`bar-btn ${activePage === id ? "bar-active" : ""}`}
          aria-current={activePage === id ? "page" : undefined}
          onClick={() => setActivePage(id)}
        >
          {label}
        </button>
      ))}
    </nav>
  );
}
