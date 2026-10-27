"""Builds the research pipeline for the web app. It only CALLS ``src/``; it never edits or reconfigures it
beyond choosing the backend. The pipeline keeps per-instance state, so one instance is built per process and
used by exactly one worker thread (see jobs.py)."""

from __future__ import annotations

import math
import re
from typing import Any

from app.config import Settings
from src.ner import EntityExtractor


# A DOSAGE match directly followed by a concentration denominator is a lab measurement, not a dose:
# "168 mg/dL", "13.5 g/dL", "140 mEq/L", "40 IU/L", "168 mg per dL". Dose rates and formulations
# ("10 mg/kg", "2 units/hr", "250 mg/5 mL") are deliberately NOT matched. (mmol/L and mmHg never match DOSAGE.)
_MEASUREMENT_AFTER_DOSE = re.compile(
    r"\s*(?:/|\bper\s+)\s*(?:dL|L|deciliters?|decilitres?|liters?|litres?)(?![A-Za-z])", re.IGNORECASE)


class AppEntityExtractor(EntityExtractor):
    """The research extractor with lab measurements removed from DOSAGE, for the app's pipeline only.

    Passed to ``FamilyCarePipeline(config, extractor=...)``; the research default extractor is unchanged."""

    def extract(self, text: str) -> list[dict[str, Any]]:
        return [e for e in super().extract(text)
                if not (e["label"] == "DOSAGE" and _MEASUREMENT_AFTER_DOSE.match(text, e["end"]))]


# The research child prompt (src/prompts.py, v2) tells the model to talk to the child as "you", which makes it address
# the child as the patient. For the app only, these exact lines are replaced in a copy of the messages.
_CHILD_YOU_RULE = '- Talk to the child as "you". Be warm and never scary.'
_CHILD_CARE_RULE = "- Say that the grown-ups and doctors are taking care of them."
_CHILD_GROUNDING_RULES = (
    "\n\nAdditional child-output safety rules for this family-care app:\n"
    "Write for a child around ages 6 to 10: use 3 to 5 short sentences and familiar, gentle words. Explain the broad "
    "meaning in a reassuring way, rather than copying clinical wording. Avoid diagnoses, medicine names, numbers, doses, "
    "hospital details, and frightening terms; the app will withhold text containing these. Do not invent what will happen. "
    "Keep the explanation useful and specific only to facts that can be said safely.\n"
    "The child reading this may be a different person from the patient in the note. Do not say that the child has or had "
    "{ref}'s condition. Refer to the patient as {ref}. Use only health facts plainly stated in the "
    "note. Do not infer a diagnosis, procedure, device, hospital event, recovery, or treatment instruction. Never advise "
    "starting, stopping, or changing medicine. If you cannot follow these rules, output only this calm message: "
    "The note has information about someone's health. Their care team can explain what it means. You can ask a trusted "
    "adult if you have questions."
)
_NOTE_BLOCK = re.compile(r'CLINICAL NOTE:\n"""\n(.*?)\n"""', re.DOTALL)
# Only an explicit "Patient:" / "Patient name:" / "Name:" line at the start of a line gives a first name.
_NAME_LINE = re.compile(r"^[\s*_#>-]*(?i:patient(?:\s+name)?|name)\s*:[\s*_]*([A-Z][a-z]+(?:[-'][A-Za-z]+)?)\b",
                        re.MULTILINE)
_NOT_NAMES = frozenset({"female", "male", "woman", "man", "girl", "boy", "adult", "child", "infant", "patient", "the",
                        "an", "mr", "mrs", "ms", "miss", "dr", "unknown", "anonymous", "none", "name", "redacted", "age"})


def _patient_reference(user_content: str) -> str:
    """The patient's first name from an explicit name line in the note, otherwise "the person"."""
    note = _NOTE_BLOCK.search(user_content)
    match = _NAME_LINE.search(note.group(1)) if note else None
    if match and match.group(1).casefold() not in _NOT_NAMES and len(match.group(1)) <= 30:
        return match.group(1)
    return "the person"


def _third_person_child_prompt(content: str) -> str:
    ref = _patient_reference(content)
    content = content.replace(_CHILD_YOU_RULE, (
        f'- Talk to the child about {ref} in the third person, for example "{ref[:1].upper() + ref[1:]} has ...". '
        f"Never tell the child that they have {ref}'s health problems. Be warm and never scary."))
    content = content.replace(_CHILD_CARE_RULE, f"- Say that the grown-ups and doctors are taking care of {ref}.")
    return content + _CHILD_GROUNDING_RULES.format(ref=ref)


_AUDIENCE = re.compile(r"^AUDIENCE: (patient|caregiver|child)\s*$", re.MULTILINE)


class _AppPromptGuard:
    """Add app-specific child grounding rules without editing the protected research prompt source.

    Also records which persona and attempt is being generated (``progress``; fixed persona names and a count only,
    never message text) so a failed job can say where it stopped. ``on_attempt`` lets the worker process report it."""

    def __init__(self, generator: Any) -> None:
        self._generator = generator
        self.progress: tuple[str, int] | None = None
        self.on_attempt: Any = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._generator, name)

    def generate(self, messages: list[dict[str, str]], **overrides: Any) -> str:
        persona = "unknown"
        for message in reversed(messages):
            if message.get("role") == "user" and "AUDIENCE:" in message.get("content", ""):
                match = _AUDIENCE.search(message["content"])
                persona = match.group(1) if match else "unknown"
                break
        self.progress = (persona, 1 + sum(1 for m in messages if m.get("role") == "assistant"))
        if self.on_attempt is not None:
            self.on_attempt(*self.progress)
        # Rewrites a copy on every call, so retries (which resend the pipeline's original messages) get it exactly once.
        guarded = [dict(message) for message in messages]
        for message in reversed(guarded):
            if message.get("role") == "user" and "AUDIENCE: child" in message.get("content", ""):
                message["content"] = _third_person_child_prompt(message["content"])
                break
        return self._generator.generate(guarded, **overrides)


def model_call_budget() -> int:
    """Most model calls one note can make: every persona, each with its first attempt plus ``max_retries`` retries."""
    from src.prompts import PERSONAS
    from src.utils import load_config

    return len(PERSONAS) * (int(load_config("config.yaml").get("max_retries", 2)) + 1)


def timeout_budget_problem(settings: Settings) -> str | None:
    """A message if the Ollama job timeout can stop a note whose every call stays just under the request timeout."""
    if settings.backend != "ollama":
        return None
    calls = model_call_budget()
    needed = calls * settings.ollama_timeout_seconds
    if settings.job_timeout_seconds >= needed:
        return None
    return (f"APP_JOB_TIMEOUT_SECONDS={settings.job_timeout_seconds} is below {calls} model calls x "
            f"APP_OLLAMA_TIMEOUT_SECONDS={settings.ollama_timeout_seconds:g} = {needed:g} seconds, so a slow note can be "
            f"stopped before its retries finish. Set APP_JOB_TIMEOUT_SECONDS to at least {math.ceil(needed)}.")


def build_pipeline(settings: Settings) -> Any:
    from src.pipeline import FamilyCarePipeline  # imported lazily: heavy, and not needed to run most tests
    from src.utils import load_config

    config = load_config("config.yaml", {"backend": settings.backend})
    extractor = AppEntityExtractor(config.get("ner", {}))
    if settings.backend == "ollama":
        from app.ollama_generator import OllamaGenerator

        generator = OllamaGenerator(
            config.get("generation", {}), url=settings.ollama_url, model=settings.ollama_model,
            timeout_seconds=settings.ollama_timeout_seconds,
            context_size=int(config.get("llama_cpp", {}).get("n_ctx", 4096)),
            allow_remote=settings.ollama_allow_remote,
        )
        return FamilyCarePipeline(config, generator=_AppPromptGuard(generator), extractor=extractor)
    if settings.backend == "mock":
        from app.mock_generator import AppMockGenerator

        generator = AppMockGenerator(config.get("generation", {}), fail_first=int(config.get("mock", {}).get("fail_first", 0)))
        return FamilyCarePipeline(config, generator=_AppPromptGuard(generator), extractor=extractor)
    pipeline = FamilyCarePipeline(config, extractor=extractor)
    pipeline.generator = _AppPromptGuard(pipeline.generator)
    return pipeline
