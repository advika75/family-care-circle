"""End-to-end pipeline: NER -> per-persona generation -> postprocessing -> validation."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.generator import Generator, build_generator
from src.matching import unique_entities
from src.ner import EntityExtractor, group_regimens
from src.postprocess import generate_with_retries, parse_checklist, redact_contradicted_dosages, validate_output
from src.prompts import PERSONAS, build_messages
from src.utils import read_text, set_seed

logger = logging.getLogger(__name__)


class FamilyCarePipeline:
    """Turns one clinical note into the three persona outputs plus entities and metadata."""

    def __init__(
        self,
        config: dict[str, Any],
        generator: Generator | None = None,
        extractor: EntityExtractor | None = None,
    ) -> None:
        self.config = config
        set_seed(int(config.get("generation", {}).get("seed", 42)))
        self.extractor = extractor or EntityExtractor(config.get("ner", {}))
        self.generator = generator or build_generator(config)
        self.max_retries = int(config.get("max_retries", 2))
        self.inject_entities = bool(config.get("prompts", {}).get("inject_entities", True))
        self.child_variant = str(config.get("prompts", {}).get("child_variant", "v2"))

    def _persona_cfg(self, persona: str) -> dict[str, Any]:
        return self.config.get("personas", {}).get(persona, {}) or {}

    def run(self, text: str, doc_id: str = "doc") -> dict[str, Any]:
        """Process one note and return the final JSON-serializable record."""
        t_start = time.perf_counter()
        entities = self.extractor.extract(text)
        regimens = group_regimens(entities, text)
        record: dict[str, Any] = {"id": doc_id}
        retries, missing, first_missing, fallbacks, latency, params = {}, {}, {}, {}, {}, {}
        first_attempt_texts, first_attempt_evidence = {}, {}
        truncated, truncated_attempts, redacted_dosages = {}, {}, {}

        for persona in PERSONAS:
            pcfg = self._persona_cfg(persona)
            required_labels = list(pcfg.get("required_labels", []))
            required = unique_entities(entities, required_labels)
            messages = build_messages(persona, text, entities, regimens, required_labels, self.inject_entities,
                                      self.child_variant)
            overrides = {k: pcfg.get(k) for k in ("max_new_tokens", "temperature", "top_p")}
            params[persona] = self.generator.params(**overrides)

            t0 = time.perf_counter()
            attempt_flags: list[bool | None] = []

            def generate(msgs: list[dict[str, str]], o: dict[str, Any] = overrides) -> str:
                text = self.generator.generate(msgs, **o)
                attempt_flags.append(self.generator.last_truncated)
                return text

            result = generate_with_retries(
                generate,
                messages,
                required,
                persona,
                self.max_retries,
                source=text,
                entities=entities,
            )
            final_text, redacted = redact_contradicted_dosages(result.text, text)
            if redacted:
                result.fallback_used = True  # a contradicted dose is a hard validation failure
            first_attempt_texts[persona] = result.first_attempt_text
            output_file_ref = f"{doc_id}.json"
            first_attempt_evidence[persona] = {
                "note_id": doc_id,
                "persona": persona,
                "model_config": {
                    "backend": self.generator.backend,
                    "model_id": self.generator.model_id,
                    "model_hash": self.generator.model_hash,
                    "generation_params": params[persona],
                    "seed": self.generator.seed,
                    "inject_entities": self.inject_entities,
                    "child_variant": self.child_variant,
                    "max_retries": self.max_retries,
                },
                "attempt_count": result.attempts,
                "first_attempt_number": 1,
                "retry_count": result.retries,
                "retry_status": result.retries > 0,
                "fallback_status": result.fallback_used,
                "output_references": {
                    "first_attempt_text": f"{output_file_ref}#/metadata/first_attempt_text/{persona}",
                    "final_output": f"{output_file_ref}#/{persona}",
                },
            }
            latency[persona] = round(time.perf_counter() - t0, 3)
            retries[persona] = result.retries
            missing[persona] = [m["text"] for m in result.missing]
            first_missing[persona] = [m["text"] for m in result.first_missing]
            fallbacks[persona] = result.fallback_used
            truncated_attempts[persona] = attempt_flags
            redacted_dosages[persona] = redacted
            # Truncation of the text that was kept (None if every attempt was empty).
            truncated[persona] = attempt_flags[result.used_attempt] if result.used_attempt is not None else None
            record[persona] = parse_checklist(final_text) if persona == "caregiver_checklist" else final_text
            logger.info("[%s] %s done in %.2fs (retries=%d)", doc_id, persona, latency[persona], result.retries)

        errors = validate_output(record)
        latency["total"] = round(time.perf_counter() - t_start, 3)
        record.update(
            {
                "entities": entities,
                "regimens": regimens,
                "source_text": text,
                "metadata": {
                    "backend": self.generator.backend,
                    "model_id": self.generator.model_id,
                    "model_hash": self.generator.model_hash,
                    "generation_params": params,
                    "seed": self.generator.seed,
                    "max_retries": self.max_retries,
                    "inject_entities": self.inject_entities,
                    "child_variant": self.child_variant,
                    "retries": retries,
                    "missing_first_attempt": first_missing,
                    "first_attempt_text": first_attempt_texts,
                    "first_attempt_evidence": first_attempt_evidence,
                    "missing_after_retries": missing,
                    "fallback_used": fallbacks,
                    "truncated": truncated,
                    "truncated_attempts": truncated_attempts,
                    "redacted_dosages": redacted_dosages,
                    "latency_sec": latency,
                    "valid": not errors,
                    "validation_errors": errors,
                    "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                },
            }
        )
        return record

    def run_file(self, path: str | Path) -> dict[str, Any]:
        """Read a note from ``path`` and process it, using the file stem as the id."""
        return self.run(read_text(path), doc_id=Path(path).stem)
