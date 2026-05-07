import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from agents.llm_clients import call_chatgpt, call_gemini, call_nvidia


MISSION = """
Design a compact autonomous rover with camera-based navigation,
ROS2 architecture, CAD concept plan, risk matrix, and validation checklist.

Include at least three unconventional design alternatives before choosing
the most practical build.
"""


def main():
    print("\n==============================")
    print("GEMINI — CREATIVE DESIGN AGENT")
    print("==============================\n")

    gemini_output = call_gemini(
        MISSION,
        system_prompt=(
            "You are OMNI's creative design expansion agent. "
            "Generate unconventional but physically plausible robot concepts. "
            "Focus on morphology, form factor, sensor placement, mobility style, "
            "and design alternatives."
        ),
    )

    print(gemini_output)

    print("\n==============================")
    print("OPENAI — STRUCTURED ARTIFACT AGENT")
    print("==============================\n")

    openai_output = call_chatgpt(
        f"""
Use the creative design ideas below and convert them into structured
engineering artifacts.

Creative ideas:
{gemini_output}

Original mission:
{MISSION}
""",
        system_prompt=(
            "You are OMNI's structured engineering artifact generator. "
            "Produce organized robotics outputs: requirements, ROS2 architecture, "
            "CAD concept plan, components, validation checklist, and risks."
        ),
    )

    print(openai_output)

    print("\n==============================")
    print("NVIDIA — ENGINEERING REVIEWER")
    print("==============================\n")

    nvidia_output = call_nvidia(
        f"""
Review this OMNI engineering output for realism, risks, missing assumptions,
fabrication concerns, and validation gaps.

Engineering output:
{openai_output}
""",
        system_prompt=(
            "You are OMNI's engineering reviewer. Be concise, practical, "
            "critical, and structured. Identify blockers, warnings, and next fixes."
        ),
    )

    print(nvidia_output)


if __name__ == "__main__":
    main()
