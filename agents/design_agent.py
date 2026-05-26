from agents.base_agent import BaseAgent
from backend.app.omni_core.llm_router import call_llm


class DesignAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Vega",
            role="Creative design, biomorphic morphology, and concept alternatives",
            system_prompt=(
                "You are Vega, OMNI's creative design and morphology intelligence. "
                "Be imaginative but physically plausible. "
                "Generate concise, dashboard-friendly design alternatives. "
                "Do not write the final engineering report."
            ),
        )

    def run(self, mission):
        prompt = f"""
You are OMNI's creative design expansion agent.

Your job is to expand the mission into physically plausible but creative design alternatives.

Focus on:
- unconventional form factors
- morphology/body shape
- mobility style
- sensor placement
- mechanical layout
- tradeoffs between creative and practical designs

Do NOT write the final engineering report.
Do NOT over-explain.
Keep the output dashboard-friendly.

Mission:
{mission}

Return this exact structure:

## Creative Design Alternatives

### Alternative 1
- Concept:
- Why it is interesting:
- Practical concerns:

### Alternative 2
- Concept:
- Why it is interesting:
- Practical concerns:

### Alternative 3
- Concept:
- Why it is interesting:
- Practical concerns:

## Recommended Direction
- Best option:
- Why:
- What Sky, Korva, Isy, Oli, and Pluto should pay attention to:
"""

        return call_llm(
            prompt,
            role="Vega", system_prompt=self.system_prompt,
        )