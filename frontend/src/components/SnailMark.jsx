// OMNI's symbolic mark. The artwork lives in public/brand/ so the favicon,
// README, and UI all share one file; replacing that SVG updates every use.
const SNAIL_MARK_SRC = `${import.meta.env.BASE_URL}brand/omni-snail-mark.svg`;
const ASPECT_RATIO = 80 / 120;

export default function SnailMark({ size = 40, className = "", decorative = false }) {
  return (
    <img
      className={className}
      src={SNAIL_MARK_SRC}
      width={size}
      height={Math.round(size * ASPECT_RATIO)}
      alt={decorative ? "" : "OMNI"}
      aria-hidden={decorative ? "true" : undefined}
      draggable="false"
    />
  );
}
