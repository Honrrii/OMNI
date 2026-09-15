import SnailMark from "../components/SnailMark.jsx";
import {
  ABOUT,
  AGENTS_SECTION,
  CAPABILITIES_SECTION,
  CAPABILITY_STATUS,
  DEMOS,
  FOOTER,
  HERO,
  LINKS,
  NAV_ITEMS,
  ROADMAP,
  SYSTEM,
} from "./siteContent.js";
import "../styles/omni-public-site.css";

function formatIndex(index) {
  return String(index + 1).padStart(2, "0");
}

function ExternalLink({ href, children, className }) {
  return (
    <a className={className} href={href} target="_blank" rel="noreferrer">
      {children}
    </a>
  );
}

function SectionHeading({ id, eyebrow, title, intro }) {
  return (
    <header className="site-section-heading">
      <p className="site-eyebrow">{eyebrow}</p>
      <h2 id={id}>{title}</h2>
      {intro && <p className="site-section-intro">{intro}</p>}
    </header>
  );
}

function DefinitionList({ items, className }) {
  return (
    <dl className={className}>
      {items.map((item) => (
        <div key={item.term}>
          <dt>{item.term}</dt>
          <dd>{item.detail}</dd>
        </div>
      ))}
    </dl>
  );
}

function SiteHeader() {
  return (
    <header className="site-header">
      <div className="site-container site-header-inner">
        <a className="site-brand" href="#top" aria-label="OMNI overview">
          <SnailMark size={34} decorative />
          <span>OMNI</span>
        </a>

        <nav className="site-nav" aria-label="Overview sections">
          {NAV_ITEMS.map((item) => (
            <a key={item.href} href={item.href}>
              {item.label}
            </a>
          ))}
        </nav>

        <a className="site-button site-button-small" href={LINKS.console}>
          Open console
        </a>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section className="site-hero" id="top" aria-labelledby="site-hero-title">
      <div className="site-container site-hero-grid">
        <div className="site-hero-copy">
          <p className="site-eyebrow">{HERO.eyebrow}</p>
          <h1 id="site-hero-title" className="site-wordmark">
            {HERO.title}
          </h1>
          <p className="site-expanded-name">{HERO.expandedName}</p>
          <p className="site-lede">{HERO.lede}</p>
          <p className="site-support">{HERO.support}</p>

          <div className="site-cta-row">
            <a className="site-button" href={LINKS.console}>
              Open console
            </a>
            <a className="site-button site-button-ghost" href="#system">
              How it works
            </a>
          </div>

          <p className="site-cta-note">
            The console connects to a locally running OMNI backend.{" "}
            <ExternalLink href={LINKS.repository}>View the source</ExternalLink>
          </p>
        </div>

        <div className="site-hero-visual" aria-hidden="true">
          <div className="site-plinth">
            <SnailMark size={340} className="site-hero-mark" decorative />
          </div>
        </div>
      </div>

      <div className="site-container">
        <DefinitionList items={HERO.facts} className="site-fact-row" />
      </div>
    </section>
  );
}

function About() {
  return (
    <section className="site-section" id="about" aria-labelledby="about-title">
      <div className="site-container site-about-grid">
        <SectionHeading id="about-title" eyebrow={ABOUT.eyebrow} title={ABOUT.title} />
        <div className="site-about-body">
          {ABOUT.paragraphs.map((paragraph) => (
            <p key={paragraph}>{paragraph}</p>
          ))}
          <DefinitionList items={ABOUT.facts} className="site-definition-list" />
        </div>
      </div>
    </section>
  );
}

function StatusLabel({ status }) {
  return (
    <span className={`site-status site-status-${status}`}>
      {CAPABILITY_STATUS[status].label}
    </span>
  );
}

function Capabilities() {
  const { eyebrow, title, intro, items } = CAPABILITIES_SECTION;

  return (
    <section
      className="site-section site-section-tinted"
      id="capabilities"
      aria-labelledby="capabilities-title"
    >
      <div className="site-container">
        <SectionHeading id="capabilities-title" eyebrow={eyebrow} title={title} intro={intro} />

        <ol className="site-capability-grid">
          {items.map((capability, index) => (
            <li key={capability.title} className="site-capability">
              <div className="site-capability-meta">
                <span className="site-index">{formatIndex(index)}</span>
                <StatusLabel status={capability.status} />
              </div>
              <h3>{capability.title}</h3>
              <p>{capability.summary}</p>
            </li>
          ))}
        </ol>

        <dl className="site-legend" aria-label="Maturity labels">
          {Object.entries(CAPABILITY_STATUS).map(([status, { definition }]) => (
            <div key={status}>
              <dt>
                <StatusLabel status={status} />
              </dt>
              <dd>{definition}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}

function Agents() {
  const { eyebrow, title, intro, core, agents } = AGENTS_SECTION;

  return (
    <section className="site-section" id="agents" aria-labelledby="agents-title">
      <div className="site-container">
        <SectionHeading id="agents-title" eyebrow={eyebrow} title={title} intro={intro} />

        <ol className="site-agent-grid">
          {agents.map((agent, index) => (
            <li key={agent.id} className="site-agent">
              <span className="site-index">{formatIndex(index)}</span>
              <h3>{agent.name}</h3>
              <p className="site-agent-role">{agent.role}</p>
              <p className="site-agent-summary">{agent.summary}</p>
            </li>
          ))}
        </ol>

        <div className="site-core-note">
          <span className="site-core-label">{core.name}</span>
          <p>{core.summary}</p>
        </div>
      </div>
    </section>
  );
}

function System() {
  return (
    <section className="site-section site-section-dark" id="system" aria-labelledby="system-title">
      <div className="site-container">
        <SectionHeading
          id="system-title"
          eyebrow={SYSTEM.eyebrow}
          title={SYSTEM.title}
          intro={SYSTEM.intro}
        />

        <ol className="site-pipeline" aria-label="Mission pipeline">
          {SYSTEM.stages.map((stage) => (
            <li key={stage.step} className="site-stage">
              <span className="site-stage-node" aria-hidden="true" />
              <span className="site-index">{stage.step}</span>
              <h3>{stage.name}</h3>
              <p className="site-stage-owner">{stage.owner}</p>
              <p className="site-stage-detail">{stage.detail}</p>
            </li>
          ))}
          <li className="site-stage site-stage-outcome">
            <span className="site-stage-node" aria-hidden="true" />
            <span className="site-index">→</span>
            <h3>{SYSTEM.outcome.name}</h3>
            <p className="site-stage-detail">{SYSTEM.outcome.detail}</p>
          </li>
        </ol>

        <ul className="site-principles">
          {SYSTEM.principles.map((principle) => (
            <li key={principle.title}>
              <h3>{principle.title}</h3>
              <p>{principle.detail}</p>
            </li>
          ))}
        </ul>

        <p className="site-footnote">{SYSTEM.footnote}</p>
      </div>
    </section>
  );
}

function Roadmap() {
  return (
    <section className="site-section" id="roadmap" aria-labelledby="roadmap-title">
      <div className="site-container">
        <SectionHeading
          id="roadmap-title"
          eyebrow={ROADMAP.eyebrow}
          title={ROADMAP.title}
          intro={ROADMAP.intro}
        />

        <ol className="site-roadmap">
          {ROADMAP.horizons.map((horizon) => (
            <li key={horizon.label} className="site-horizon">
              <p className="site-horizon-label">{horizon.label}</p>
              <h3>{horizon.title}</h3>
              <ul>
                {horizon.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </li>
          ))}
        </ol>

        <blockquote className="site-motto">
          <p>{ROADMAP.motto}</p>
        </blockquote>
      </div>
    </section>
  );
}

function Demos() {
  return (
    <section className="site-section site-section-tinted" id="demos" aria-labelledby="demos-title">
      <div className="site-container">
        <SectionHeading id="demos-title" eyebrow={DEMOS.eyebrow} title={DEMOS.title} intro={DEMOS.intro} />

        <ul className="site-demo-grid">
          {DEMOS.placeholders.map((label) => (
            <li key={label} className="site-demo-frame">
              <span>{label}</span>
              <small>Coming soon</small>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-container site-footer-inner">
        <div className="site-footer-brand">
          <SnailMark size={44} decorative />
          <div>
            <p className="site-footer-name">OMNI</p>
            <p className="site-footer-expanded">{HERO.expandedName}</p>
          </div>
        </div>

        <p className="site-footer-note">{FOOTER.note}</p>

        <nav className="site-footer-links" aria-label="Footer">
          <a href={LINKS.console}>Console</a>
          <ExternalLink href={LINKS.repository}>GitHub</ExternalLink>
        </nav>
      </div>
    </footer>
  );
}

export default function PublicHome() {
  return (
    <div className="site">
      <SiteHeader />
      <main>
        <Hero />
        <About />
        <Capabilities />
        <Agents />
        <System />
        <Roadmap />
        <Demos />
      </main>
      <SiteFooter />
    </div>
  );
}
