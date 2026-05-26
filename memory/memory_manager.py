import json
from datetime import datetime
from pathlib import Path


MEMORY_DIR = Path("memory")
MEMORY_FILE = MEMORY_DIR / "omni_memory.json"

MAX_MISSIONS_TO_KEEP = 25
MAX_MEMORY_SEEDS_TO_KEEP = 100
MAX_SUMMARY_CHARS = 1400
MAX_MISSION_CHARS = 500


def ensure_memory_file():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    if not MEMORY_FILE.exists():
        save_memory({"missions": []})


def load_memory():
    ensure_memory_file()

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return {"missions": []}

        if "missions" not in data or not isinstance(data["missions"], list):
            data["missions"] = []

        return data

    except json.JSONDecodeError:
        return {"missions": []}


def save_memory(memory):
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=4)


def clean_text(text, max_chars):
    if text is None:
        return ""

    value = str(text).strip()

    # Remove excessive blank lines.
    while "\n\n\n" in value:
        value = value.replace("\n\n\n", "\n\n")

    if len(value) > max_chars:
        value = value[:max_chars].rstrip() + "\n...[truncated]"

    return value


def extract_key_lines(summary):
    """
    Keeps memory useful without storing full agent reports.
    It looks for the most important mission-memory signals.
    """
    if not summary:
        return "No summary provided."

    text = str(summary)

    useful_markers = [
        "Revision Risk Level:",
        "Revision Required Fixes:",
        "QaZ Validation Verdict:",
        "QaZ Score:",
        "QaZ Missing Evidence:",
        "QaZ Required Next Tests:",
    ]

    extracted = []

    for line in text.splitlines():
        stripped = line.strip()

        if any(stripped.startswith(marker) for marker in useful_markers):
            extracted.append(stripped)

    if extracted:
        return "\n".join(extracted)

    return clean_text(text, MAX_SUMMARY_CHARS)


def add_mission_to_memory(mission, summary):
    memory = load_memory()

    compact_entry = {
        "timestamp": datetime.now().isoformat(),
        "mission": clean_text(mission, MAX_MISSION_CHARS),
        "summary": clean_text(extract_key_lines(summary), MAX_SUMMARY_CHARS),
    }

    memory["missions"].append(compact_entry)

    # Prevent memory file from growing forever.
    memory["missions"] = memory["missions"][-MAX_MISSIONS_TO_KEEP:]

    save_memory(memory)


def get_recent_memory(n=5):
    memory = load_memory()
    recent = memory["missions"][-n:]

    if not recent:
        return "No previous mission memory yet."

    memory_blocks = []

    for item in recent:
        mission = clean_text(item.get("mission", ""), MAX_MISSION_CHARS)
        summary = clean_text(item.get("summary", ""), MAX_SUMMARY_CHARS)
        timestamp = item.get("timestamp", "unknown time")

        memory_blocks.append(
            f"""
Previous Mission Timestamp:
{timestamp}

Previous Mission:
{mission}

Compact Summary:
{summary}
""".strip()
        )

    return "\n\n---\n\n".join(memory_blocks)


def clear_memory():
    save_memory({"missions": []})


def get_memory_stats():
    memory = load_memory()

    return {
        "mission_count": len(memory.get("missions", [])),
        "memory_file": str(MEMORY_FILE),
        "max_missions_to_keep": MAX_MISSIONS_TO_KEEP,
    }


def add_mission_memory_seed(seed: dict, mission: str = "") -> bool:
    """
    Append a compact mission_memory_seed record to omni_memory.json.

    Returns True on successful write, False on any failure.
    Never raises.
    """
    try:
        if not isinstance(seed, dict):
            return False
        if seed.get("status") == "empty":
            return False

        memory = load_memory()
        seeds = memory.get("memory_seeds", [])
        if not isinstance(seeds, list):
            seeds = []

        mission_clean = clean_text(mission, MAX_MISSION_CHARS)
        summary = seed.get("memory_summary", "") or ""

        # Deduplicate: skip if same (mission, memory_summary) already stored.
        for existing in seeds:
            if (existing.get("mission") == mission_clean and
                    existing.get("memory_summary") == summary):
                return False

        record = {
            "type": "mission_memory_seed",
            "timestamp": datetime.now().isoformat(),
            "mission": mission_clean,
            "mission_type": seed.get("mission_type"),
            "platform_intent": seed.get("platform_intent"),
            "recommended_candidate_id": seed.get("recommended_candidate_id"),
            "risk_level": seed.get("risk_level"),
            "safety_status": seed.get("safety_status"),
            "required_human_review": bool(seed.get("required_human_review", False)),
            "unresolved_questions": list(seed.get("unresolved_questions") or []),
            "recurring_risk_themes": list(seed.get("recurring_risk_themes") or []),
            "next_design_lessons": list(seed.get("next_design_lessons") or []),
            "memory_summary": summary,
        }

        seeds.append(record)
        # Cap to the most recent MAX_MEMORY_SEEDS_TO_KEEP entries.
        seeds = seeds[-MAX_MEMORY_SEEDS_TO_KEEP:]
        memory["memory_seeds"] = seeds
        save_memory(memory)
        return True

    except Exception:
        return False


def get_recent_memory_seeds(n: int = 5) -> list:
    """Return up to n most recent mission_memory_seed records (newest last)."""
    try:
        memory = load_memory()
        seeds = memory.get("memory_seeds", [])
        if not isinstance(seeds, list):
            return []
        return seeds[-n:]
    except Exception:
        return []


def get_recent_memory_seed_context(n: int = 5) -> str:
    """
    Return a compact human-readable text block from recent mission memory seeds.

    Suitable for injection into agent prompts as lightweight prior-mission context.
    Returns "" if no seeds exist or on any error.
    Never raises.
    """
    try:
        if n <= 0:
            return ""
        seeds = get_recent_memory_seeds(n)
        if not seeds:
            return ""

        lines = [f"Recent OMNI mission lessons ({len(seeds)}):"]

        # Present newest first so the most relevant lesson appears first.
        for seed in reversed(seeds):
            mission_type    = seed.get("mission_type") or "unknown"
            platform        = seed.get("platform_intent") or "unknown"
            safety_status   = seed.get("safety_status") or "unknown"
            risk_level      = seed.get("risk_level") or "unknown"
            human_review    = "human review required" if seed.get("required_human_review") else "no human review"
            lessons         = seed.get("next_design_lessons") or []
            summary         = str(seed.get("memory_summary") or "").strip()

            # Compact one-line header.
            header = (
                f"- {mission_type} / {platform}: "
                f"Pluto {safety_status}/{risk_level}, {human_review}."
            )

            # Append up to three lessons, each capped at 80 chars.
            if lessons:
                lesson_text = "; ".join(
                    str(l).strip()[:80] for l in lessons[:3] if str(l).strip()
                )
                if lesson_text:
                    header += f" Lesson: {lesson_text}"

            lines.append(header)

            # One-line summary (max 200 chars) on indented follow-up line.
            if summary:
                lines.append(f"  {summary[:200]}")

        return "\n".join(lines)

    except Exception:
        return ""