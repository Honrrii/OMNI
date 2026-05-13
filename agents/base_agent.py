# agents/base_agent.py

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from backend.app.omni_core.llm_router import call_llm


class StructuredAgentMixin:
    """
    Week 2 structured agent contract.

    Agents can implement:
    - build_prompt(state)
    - parse_output(raw, state)

    This mixin also provides a safe JSON parser fallback.
    """

    agent_id: str = "agent"
    agent_name: str = "Agent"
    role: str = "general"

    def build_prompt(self, state: Any) -> str:
        mission_text = getattr(state, "mission_text", str(state))
        return str(mission_text)

    def parse_output(self, raw: Any, state: Any = None) -> Dict[str, Any]:
        """
        Default structured parser.

        Tries:
        1. Full JSON response
        2. JSON inside markdown/text
        3. Raw fallback wrapper
        """
        if isinstance(raw, dict):
            raw.setdefault("agent_id", self.agent_id)
            raw.setdefault("role", self.role)
            raw.setdefault("status", "structured")
            return raw

        text = str(raw or "").strip()

        if not text:
            return {
                "agent_id": self.agent_id,
                "role": self.role,
                "status": "empty_output",
                "content": {},
                "warnings": ["Agent returned empty output."],
            }

        if text.startswith("```"):
            text = text.strip("`").strip()
            if text.lower().startswith("json"):
                text = text[4:].strip()

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                parsed.setdefault("agent_id", self.agent_id)
                parsed.setdefault("role", self.role)
                parsed.setdefault("status", "structured")
                return parsed
        except json.JSONDecodeError:
            pass

        json_match = re.search(r"\{.*\}", text, re.DOTALL)

        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                if isinstance(parsed, dict):
                    parsed.setdefault("agent_id", self.agent_id)
                    parsed.setdefault("role", self.role)
                    parsed.setdefault("status", "structured")
                    return parsed
            except json.JSONDecodeError:
                pass

        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "status": "unstructured_fallback",
            "content": {
                "raw_report": str(raw or ""),
            },
            "warnings": [
                "Agent did not return valid JSON. Stored raw output fallback."
            ],
        }


class BaseAgent(StructuredAgentMixin):
    """
    Backwards-compatible base class for existing OMNI agents.

    This keeps old files working when they do:

        from agents.base_agent import BaseAgent

    and also supports the new Week 2 structured methods.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        role: Optional[str] = None,
        system_prompt: Optional[str] = None,
        agent_id: Optional[str] = None,
        **kwargs,
    ):
        self.name = name or getattr(self, "agent_name", self.__class__.__name__)
        self.agent_name = self.name
        self.role = role or getattr(self, "role", "general")
        self.agent_id = agent_id or getattr(
            self,
            "agent_id",
            self.name.lower().replace(" ", "_"),
        )
        self.system_prompt = system_prompt or getattr(self, "system_prompt", "")

        # Preserve any extra fields older agents may pass in.
        for key, value in kwargs.items():
            setattr(self, key, value)

    def build_prompt(self, state: Any) -> str:
        """
        Default state-aware prompt builder.

        Individual agents can override this later.
        """
        mission_text = getattr(state, "mission_text", str(state))

        if self.system_prompt:
            return f"""
{self.system_prompt}

Mission:
{mission_text}
"""

        return str(mission_text)

    def run(self, prompt: str) -> str:
        """
        Default legacy run method.

        Existing agents that do not override run() can still call the LLM.
        Existing agents that already override run() will keep their own behavior.
        """
        return call_llm(prompt, role=self.agent_name)

    def parse_output(self, raw: Any, state: Any = None) -> Dict[str, Any]:
        """
        Uses StructuredAgentMixin parser.
        """
        return super().parse_output(raw, state)