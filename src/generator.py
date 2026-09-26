"""Text generation backends behind one small interface.

Backends (``backend`` in config.yaml):
  * ``transformers`` - Hugging Face causal LM, prompt built with ``tokenizer.apply_chat_template``.
  * ``llama_cpp``    - llama-cpp-python with a local GGUF file.
  * ``mock``         - deterministic template output; needs no model (used by tests and demos).

Heavy libraries are imported inside each backend so the mock path only needs the standard library.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from src.utils import resolve_path, set_seed

logger = logging.getLogger(__name__)

Messages = list[dict[str, str]]


def _version_tuple(version: str) -> tuple[int, ...]:
    """'4.56.1' -> (4, 56, 1); non-numeric suffixes are ignored."""
    return tuple(int(p) for p in version.split(".")[:3] if p.isdigit())


class Generator(ABC):
    """Common interface: turn chat messages into a completion string."""

    backend: str = "base"

    def __init__(self, model_id: str, generation_cfg: dict[str, Any]) -> None:
        self.model_id = model_id
        self.configure(generation_cfg)

    #: Whether the most recent generate() call stopped because it hit max_new_tokens (None = unknown).
    last_truncated: bool | None = None

    def configure(self, generation_cfg: dict[str, Any]) -> None:
        """(Re)set default generation parameters and seed, e.g. to reuse a loaded model across runs."""
        self.defaults = {
            "max_new_tokens": int(generation_cfg.get("max_new_tokens", 400)),
            "temperature": float(generation_cfg.get("temperature", 0.2)),
            "top_p": float(generation_cfg.get("top_p", 0.9)),
        }
        self.seed = int(generation_cfg.get("seed", 42))

    def params(self, **overrides: Any) -> dict[str, Any]:
        """Default generation parameters updated with non-None ``overrides``."""
        merged = dict(self.defaults)
        merged.update({k: v for k, v in overrides.items() if v is not None and k in merged})
        return merged

    @abstractmethod
    def generate(self, messages: Messages, **overrides: Any) -> str:
        """Generate a reply to ``messages``. ``overrides`` may set max_new_tokens/temperature/top_p."""


class TransformersGenerator(Generator):
    """Hugging Face ``AutoModelForCausalLM`` backend."""

    backend = "transformers"

    def __init__(self, model_id: str, generation_cfg: dict[str, Any], hf_cfg: dict[str, Any] | None = None) -> None:
        super().__init__(model_id, generation_cfg)
        import torch
        import transformers
        from transformers import AutoModelForCausalLM, AutoTokenizer

        hf_cfg = hf_cfg or {}
        self._torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        # transformers >= 4.56 renamed `torch_dtype` to `dtype`
        dtype_key = "dtype" if _version_tuple(transformers.__version__) >= (4, 56) else "torch_dtype"
        kwargs: dict[str, Any] = {
            "device_map": hf_cfg.get("device_map", "auto"),
            dtype_key: hf_cfg.get("torch_dtype", "auto"),
        }
        if hf_cfg.get("load_in_4bit"):
            quant = self._four_bit_config()
            if quant is not None:
                kwargs["quantization_config"] = quant
        logger.info("Loading %s (this can take a while the first time)...", model_id)
        self.model = AutoModelForCausalLM.from_pretrained(model_id, **kwargs)
        self.model.eval()
        offloaded = {d for d in (getattr(self.model, "hf_device_map", None) or {}).values() if d in ("cpu", "disk")}
        if offloaded:
            logger.warning(
                "Model does not fit in accelerator memory; some layers are on %s, so generation will be very "
                "slow. Use a smaller model or the llama_cpp backend with a quantized GGUF.", "/".join(sorted(offloaded))
            )

    def _four_bit_config(self) -> Any | None:
        """Return a BitsAndBytesConfig if bitsandbytes + CUDA are available, else None (with a warning)."""
        try:
            import bitsandbytes  # noqa: F401
            from transformers import BitsAndBytesConfig
        except ImportError:
            logger.warning("load_in_4bit requested but bitsandbytes is not installed; loading full precision.")
            return None
        if not self._torch.cuda.is_available():
            logger.warning("load_in_4bit requires a CUDA GPU; loading full precision.")
            return None
        return BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=self._torch.bfloat16
        )

    def _encode(self, messages: Messages) -> dict[str, Any]:
        """Apply the model's own chat template; fold the system prompt into the user turn if unsupported."""
        kwargs = {"add_generation_prompt": True, "return_tensors": "pt", "return_dict": True}
        try:
            return self.tokenizer.apply_chat_template(messages, **kwargs)
        except Exception:  # noqa: BLE001 - e.g. templates that reject a "system" role
            if not messages or messages[0]["role"] != "system":
                raise
            system, rest = messages[0]["content"], [dict(m) for m in messages[1:]]
            rest[0]["content"] = f"{system}\n\n{rest[0]['content']}"
            return self.tokenizer.apply_chat_template(rest, **kwargs)

    def generate(self, messages: Messages, **overrides: Any) -> str:
        p = self.params(**overrides)
        set_seed(self.seed)
        inputs = {k: v.to(self.model.device) for k, v in self._encode(messages).items()}
        gen_kwargs: dict[str, Any] = {
            "max_new_tokens": p["max_new_tokens"],
            "do_sample": p["temperature"] > 0,
            "pad_token_id": self.tokenizer.pad_token_id or self.tokenizer.eos_token_id,
        }
        if gen_kwargs["do_sample"]:
            gen_kwargs.update(temperature=p["temperature"], top_p=p["top_p"])
        with self._torch.no_grad():
            output = self.model.generate(**inputs, **gen_kwargs)
        new_tokens = output[0, inputs["input_ids"].shape[1]:]
        self.last_truncated = self._hit_limit(new_tokens.tolist(), p["max_new_tokens"])
        return self.tokenizer.decode(new_tokens, skip_special_tokens=True)

    def _hit_limit(self, token_ids: list[int], max_new_tokens: int) -> bool:
        """True if generation used every allowed token without emitting an end-of-sequence token."""
        eos = self.model.generation_config.eos_token_id
        if eos is None:
            eos = self.tokenizer.eos_token_id
        eos_ids = set(eos) if isinstance(eos, (list, tuple)) else {eos}
        return len(token_ids) >= max_new_tokens and not eos_ids.intersection(token_ids)


class LlamaCppGenerator(Generator):
    """llama-cpp-python backend for local GGUF models."""

    backend = "llama_cpp"

    def __init__(self, gguf_path: str, generation_cfg: dict[str, Any], cpp_cfg: dict[str, Any] | None = None) -> None:
        super().__init__(str(gguf_path), generation_cfg)
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise ImportError("llama_cpp backend needs `pip install llama-cpp-python`.") from exc
        path = resolve_path(gguf_path)
        if not path.exists():
            raise FileNotFoundError(f"GGUF model not found: {path} (set gguf_path in config.yaml)")
        cpp_cfg = cpp_cfg or {}
        self.llm = Llama(
            model_path=str(path),
            n_ctx=int(cpp_cfg.get("n_ctx", 4096)),
            n_gpu_layers=int(cpp_cfg.get("n_gpu_layers", -1)),
            seed=self.seed,
            verbose=False,
        )

    def generate(self, messages: Messages, **overrides: Any) -> str:
        p = self.params(**overrides)
        result = self.llm.create_chat_completion(
            messages=messages, max_tokens=p["max_new_tokens"], temperature=p["temperature"], top_p=p["top_p"],
            seed=self.seed,
        )
        choice = result["choices"][0]
        self.last_truncated = choice.get("finish_reason") == "length"
        return choice["message"].get("content") or ""


class MockGenerator(Generator):
    """Deterministic, model-free backend.

    It reads the persona (``AUDIENCE:`` line) and the MUST INCLUDE block from the prompt and fills
    a fixed template, so the full pipeline, retries and evaluation can run without downloads.
    ``fail_first=N`` makes the first N calls for each persona return an empty string.
    """

    backend = "mock"

    def __init__(self, generation_cfg: dict[str, Any] | None = None, fail_first: int = 0) -> None:
        super().__init__("mock", generation_cfg or {})
        self.fail_first = fail_first
        self.calls: dict[str, int] = {}

    def generate(self, messages: Messages, **overrides: Any) -> str:
        prompt = next((m["content"] for m in messages if m["role"] == "user" and "AUDIENCE:" in m["content"]), "")
        persona_match = re.search(r"AUDIENCE:\s*(\w+)", prompt)
        persona = persona_match.group(1) if persona_match else "patient"
        self.calls[persona] = self.calls.get(persona, 0) + 1
        self.last_truncated = False
        if self.calls[persona] <= self.fail_first:
            return ""
        facts = _parse_prompt_facts(prompt)
        writer = {"patient": _mock_patient, "caregiver": _mock_caregiver, "child": _mock_child}.get(persona, _mock_patient)
        text = writer(facts)
        # Simulate the token limit with words, so truncation handling can be tested without a model.
        limit = self.params(**overrides)["max_new_tokens"]
        words = text.split(" ")
        if len(words) > limit:
            self.last_truncated = True
            text = " ".join(words[:limit])
        return text


def _parse_prompt_facts(prompt: str) -> dict[str, Any]:
    """Pull regimens, other required items and health problems out of a persona prompt."""
    facts: dict[str, Any] = {"regimens": [], "other": [], "problems": [], "symptoms": []}
    for line in prompt.splitlines():
        line = line.strip()
        if line.startswith("- Medication:"):
            reg: dict[str, str] = {}
            for part in line[2:].split(" | "):
                key, _, value = part.partition(":")
                reg[key.strip().lower()] = value.strip()
            facts["regimens"].append(reg)
        elif line.startswith("- Other"):
            facts["other"].append(line.split(":", 1)[1].strip())
        elif line.startswith("Health problems:"):
            facts["problems"] = [p.strip() for p in line.split(":", 1)[1].split(";") if p.strip()]
        elif line.startswith("Symptoms mentioned:"):
            facts["symptoms"] = [p.strip() for p in line.split(":", 1)[1].split(";") if p.strip()]
    return facts


def _plain(value: str) -> str:
    """Prefer the plain-English gloss in parentheses: 'BID (twice a day)' -> 'twice a day'."""
    return re.sub(r"\b[\w-]+ \(([^)]+)\)", r"\1", value)


def _regimen_sentence(reg: dict[str, str], verb: str) -> str:
    parts = [f"{verb} {reg['medication'].lower()}"]
    if reg.get("dose"):
        parts.append(reg["dose"])
    if reg.get("how often"):
        parts.append(_plain(reg["how often"]))
    if reg.get("how long"):
        parts.append(f"for {reg['how long']}")
    return ", ".join(parts) + "."


def _mock_patient(facts: dict[str, Any]) -> str:
    problems = " and ".join(p.lower() for p in facts["problems"][:2]) or "a health problem your care team is treating"
    lines = [
        "We know a visit to the doctor can feel like a lot, so here is a simple summary.",
        f"What is going on: your care team found {problems}. This can be treated, and you are not alone.",
    ]
    if facts["regimens"]:
        lines.append("Your medicines:")
        lines += [_regimen_sentence(r, "Take") for r in facts["regimens"]]
    lines += [f"Also remember: {_plain(o)}." for o in facts["other"]]
    lines.append("If you feel worse or have questions, please call your care team.")
    return "\n".join(lines)


def _mock_caregiver(facts: dict[str, Any]) -> str:
    bullets = [_regimen_sentence(r, "Give") for r in facts["regimens"]]
    bullets += [f"Keep track of: {_plain(o)}." for o in facts["other"]]
    watch = ", ".join(s.lower() for s in facts["symptoms"][:3])
    if watch:
        bullets.append(f"Watch for {watch} and note if they get worse.")
    bullets += [
        "Keep a written log of each dose you give.",
        "Call the care team if things get worse or you have questions.",
        "Schedule and keep all follow-up visits.",
    ]
    return "\n".join(f"- {b}" for b in bullets)


def _mock_child(facts: dict[str, Any]) -> str:
    return (
        "Your body has been feeling a little sick. That is okay.\n"
        "Think of your body like a castle. Germs or aches are like pesky visitors.\n"
        "Your medicine is like a team of tiny helpers. They help your castle get strong again.\n"
        "The doctors and your grown-ups are taking good care of you.\n"
        "Rest, drink water, and ask for a big hug. You will feel better soon."
    )


def build_generator(config: dict[str, Any]) -> Generator:
    """Instantiate the backend named in ``config['backend']``."""
    backend = config.get("backend", "mock")
    generation_cfg = config.get("generation", {})
    if backend == "transformers":
        return TransformersGenerator(config["model_id"], generation_cfg, config.get("transformers", {}))
    if backend == "llama_cpp":
        return LlamaCppGenerator(config["gguf_path"], generation_cfg, config.get("llama_cpp", {}))
    if backend == "mock":
        return MockGenerator(generation_cfg, fail_first=int(config.get("mock", {}).get("fail_first", 0)))
    raise ValueError(f"Unknown backend '{backend}'. Use transformers, llama_cpp or mock.")
