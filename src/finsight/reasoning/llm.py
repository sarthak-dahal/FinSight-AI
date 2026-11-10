"""Thin client for a local LLM served by Ollama.

Settings live in configs/llm.yaml. The rest of the code only uses `LLMClient.chat()`,
so swapping the model (or later the runner) is a config change.
"""

from __future__ import annotations

from dataclasses import dataclass

import ollama
import yaml

from finsight.retrieval.common import PROJECT_DIR

CONFIG_PATH = PROJECT_DIR / "configs" / "llm.yaml"


class LLMUnavailable(RuntimeError):
    """Ollama is not running, or the configured model is not pulled."""


@dataclass
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int       # tokens the model actually read — compare to num_ctx to spot truncation
    completion_tokens: int
    seconds: float


def load_llm_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text())


class LLMClient:
    def __init__(self, model: str | None = None, **overrides):
        self.cfg = {**load_llm_config(), **overrides}
        if model:
            self.cfg["model"] = model
        self.model = self.cfg["model"]
        self._client = ollama.Client(host=self.cfg["host"], timeout=self.cfg["timeout"])

    def available_models(self) -> list[str]:
        """Models pulled in Ollama, sorted. Raises LLMUnavailable if Ollama isn't reachable."""
        try:
            return sorted(m.model for m in self._client.list().models if m.model)
        except Exception as e:  # connection refused, timeout, ...
            raise LLMUnavailable(
                f"Ollama not reachable at {self.cfg['host']} ({e}). Open Ollama.app or run `ollama serve`."
            ) from e

    def check(self) -> None:
        """Raise LLMUnavailable with a fix-it message if the server or model is missing."""
        names = self.available_models()
        if self.model not in names:
            raise LLMUnavailable(f"Model {self.model} not pulled. Run: ollama pull {self.model}")

    def chat(self, user: str, system: str | None = None, temperature: float | None = None) -> LLMResponse:
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
        try:
            r = self._client.chat(
                model=self.model,
                messages=messages,
                keep_alive=self.cfg["keep_alive"],
                options={
                    "num_ctx": self.cfg["num_ctx"],
                    "temperature": self.cfg["temperature"] if temperature is None else temperature,
                    "seed": self.cfg["seed"],
                },
            )
        except ollama.ResponseError as e:
            raise LLMUnavailable(f"{e}. Is {self.model} pulled? (ollama pull {self.model})") from e
        except Exception as e:
            raise LLMUnavailable(f"Ollama request failed: {e}") from e

        prompt_tokens = int(r.prompt_eval_count or 0)
        num_ctx = int(self.cfg["num_ctx"])
        if prompt_tokens >= num_ctx:
            raise RuntimeError(
                f"Prompt filled the whole context ({prompt_tokens} >= num_ctx {num_ctx}); "
                "Ollama likely truncated it. Raise num_ctx in configs/llm.yaml or send fewer chunks."
            )
        return LLMResponse(
            text=(r.message.content or "").strip(),
            model=r.model or self.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=r.eval_count or 0,
            seconds=(r.total_duration or 0) / 1e9,
        )
