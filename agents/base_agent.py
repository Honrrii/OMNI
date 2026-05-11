from typing import Any, Optional


class BaseAgent:
    """
    Base class for all OMNI agents.

    This class stores shared identity fields, but it does NOT provide fake
    agent behavior. Every real agent must implement its own run() method.

    Why:
    - Returning placeholder text hides broken agents.
    - A missing run() should fail clearly during development.
    - The supervisor should only receive real agent output or an explicit fallback.
    """

    def __init__(
        self,
        name: str,
        role: str,
        system_prompt: Optional[str] = None,
    ):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt or ""

    def describe(self) -> dict[str, str]:
        """
        Small helper for debugging, dashboards, or future AgentCouncil metadata.
        """
        return {
            "name": self.name,
            "role": self.role,
            "system_prompt": self.system_prompt,
        }

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """
        Every concrete OMNI agent must override this method.

        Do not return placeholder output here. If this method is reached,
        the agent is incomplete and should fail loudly.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement run(). "
            f"Agent name: {self.name}. Role: {self.role}."
        )
