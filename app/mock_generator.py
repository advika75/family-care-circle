"""App-specific deterministic mock outputs; the protected research generator stays unchanged."""

from __future__ import annotations

import re
from typing import Any

from src.generator import MockGenerator, _parse_prompt_facts

from app.safety import SAFE_CHILD_MESSAGE


_NOTE_BLOCK = re.compile(r'CLINICAL NOTE:\s*"""\s*(.*?)\s*"""', re.DOTALL)
_ACTION = re.compile(r"\b(?:call|contact|return|follow[- ]?up|schedule|monitor|watch for|seek care|come back)\b", re.I)


class AppMockGenerator(MockGenerator):
    """Mock backend tuned for the web app's three audiences, using only prompt-extracted note facts.

    The parent supplies the existing deterministic call accounting, failure simulation and model params.
    This class changes only the app's mock path; research runs continue to use ``src.generator.MockGenerator``.
    """

    def generate(self, messages, **overrides: Any) -> str:
        prompt = next((m["content"] for m in messages if m["role"] == "user" and "AUDIENCE:" in m["content"]), "")
        match = re.search(r"AUDIENCE:\s*(\w+)", prompt)
        audience = match.group(1) if match else "patient"
        parent_text = super().generate(messages, **overrides)
        if not parent_text:
            return ""

        facts = _parse_prompt_facts(prompt)
        note_match = _NOTE_BLOCK.search(prompt)
        note_text = note_match.group(1) if note_match else ""
        explicit_actions = []
        if note_match:
            for sentence in re.split(r"(?<=[.!?])\s+|\n+", note_match.group(1)):
                sentence = sentence.strip()
                if sentence and _ACTION.search(sentence):
                    explicit_actions.append(sentence)

        if audience == "caregiver":
            text = self._caregiver(facts, explicit_actions)
        elif audience == "child":
            text = self._child(facts, note_text)
        else:
            text = self._patient(facts, explicit_actions)

        limit = self.params(**overrides)["max_new_tokens"]
        words = text.split()
        self.last_truncated = len(words) > limit
        return " ".join(words[:limit]) if self.last_truncated else text

    @staticmethod
    def _patient(facts: dict[str, Any], actions: list[str]) -> str:
        lines = ["It can be a lot to take in. Here is what the note says."]
        problems = facts.get("problems", [])
        symptoms = facts.get("symptoms", [])
        if problems:
            lines.append("The note lists: " + "; ".join(problems[:3]) + ".")
        if symptoms:
            lines.append("It also mentions: " + "; ".join(symptoms[:3]) + ".")
        for regimen in facts.get("regimens", []):
            detail = ", ".join(regimen.get(k, "") for k in ("medication", "dose", "how often", "how long") if regimen.get(k))
            if detail:
                lines.append("Your note lists this medicine plan: " + detail + ".")
        for action in actions[:3]:
            lines.append("Next step stated in the note: " + action)
        lines.append("Ask your care team about anything unclear.")
        return "\n".join(lines)

    @staticmethod
    def _caregiver(facts: dict[str, Any], actions: list[str]) -> str:
        items = []
        for regimen in facts.get("regimens", []):
            detail = ", ".join(regimen.get(k, "") for k in ("medication", "dose", "how often", "how long") if regimen.get(k))
            if detail:
                items.append(f"- Follow the note's listed medicine plan: {detail}.")
        items.extend(f"- Follow this instruction from the note: {action}" for action in actions[:5])
        if not items:
            items.append("- Review the note's care steps with the care team.")
        return "\n".join(items)

    @staticmethod
    def _child(facts: dict[str, Any], note_text: str) -> str:
        # The deterministic demo has no semantic verifier. Use the approved non-diagnostic message.
        return SAFE_CHILD_MESSAGE
