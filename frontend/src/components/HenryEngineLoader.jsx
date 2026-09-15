import { useEffect, useState } from "react";
import SnailMark from "./SnailMark.jsx";

export default function HenryEngineLoader({ isRunning, missionText }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!isRunning) return;
    const started = Date.now();
    const timer = setInterval(
      () => setElapsed(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    return () => clearInterval(timer);
  }, [isRunning]);
  return (
    <section className="mission-progress" aria-label="Mission execution">
      <SnailMark size={40} decorative />
      <div>
        <p role="status">OMNI is processing your mission</p>
        <p>{missionText}</p>
        <small>
          Waiting for the backend result. Detailed stage progress is not
          available.
        </small>
      </div>
      <span aria-label={`${elapsed} seconds elapsed`}>{elapsed}s</span>
    </section>
  );
}
