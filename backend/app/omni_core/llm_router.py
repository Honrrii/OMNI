from __future__ import annotations

from typing import Any, Optional

from agents.llm_clients import call_chatgpt, call_gemini, call_nvidia


class LLMRouter:
    """
    Unified LLM routing wrapper for OMNI.

    Week 1 goal:
    - Centralize provider selection.
    - Keep old agents working.
    - Avoid rewriting every raw LLM call at once.

    Later this can handle:
    - retries
    - token budgets
    - model selection
    - structured JSON mode
    - telemetry
    """

    DEFAULT_ROLE_PROVIDER = {
        "Omni": "openai",
        "Echo": "openai",
        "Sky": "openai",
        "Korva": "openai",
        "Isy": "openai",
        "Oli": "openai",
        "Vega": "gemini",
        "Pluto": "openai",
        "QaZ": "openai",
    }

    def call(
        self,
        prompt: str,
        role: Optional[str] = None,
        provider: Optional[str] = None,
        system_prompt: Optional[str] = None,
        fallback_provider: str = "openai",
        **kwargs: Any,
    ) -> str:
        """
        Route an LLM call by explicit provider or OMNI agent role.

        Args:
            prompt: Full prompt string.
            role: OMNI agent name, such as Omni, Sky, Vega, Pluto.
            provider: Explicit override: openai, gemini, or nvidia.
            system_prompt: Optional system prompt passed to provider.
            fallback_provider: Used when role is unknown.

        Returns:
            Model response text.
        """
        selected_provider = (
            provider
            or self.DEFAULT_ROLE_PROVIDER.get(str(role or ""), fallback_provider)
        )

        selected_provider = selected_provider.lower().strip()

        if selected_provider == "openai":
            return call_chatgpt(prompt, system_prompt=system_prompt) or ""

        if selected_provider == "gemini":
            return call_gemini(prompt, system_prompt=system_prompt) or ""

        if selected_provider == "nvidia":
            return call_nvidia(prompt, system_prompt=system_prompt) or ""

        raise ValueError(f"Unsupported LLM provider: {selected_provider}")


llm_router = LLMRouter()


def call_llm(
    prompt: str,
    role: Optional[str] = None,
    provider: Optional[str] = None,
    system_prompt: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """
    Convenience wrapper for modules that do not need to instantiate LLMRouter.
    """
    return llm_router.call(
        prompt=prompt,
        role=role,
        provider=provider,
        system_prompt=system_prompt,
        **kwargs,
    )
