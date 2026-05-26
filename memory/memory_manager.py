import json
from datetime import datetime
from pathlib import Path


MEMORY_DIR = Path("memory")
MEMORY_FILE = MEMORY_DIR / "omni_memory.json"

MAX_MISSIONS_TO_KEEP = 25
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