"""Configuration management for Aura."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_FILENAME = "aura.toml"
DEFAULT_CONFIG_PATHS = [
    Path.cwd() / CONFIG_FILENAME,
    Path.home() / ".config" / "aura" / CONFIG_FILENAME,
]


PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "ollama": {"api_base": "http://localhost:11434", "model": "llama3"},
    "openai": {"api_base": "", "model": "gpt-4o-mini"},
    "anthropic": {"api_base": "", "model": "claude-3-haiku-20240307"},
}


@dataclass
class AIConfig:
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key: str = ""
    api_base: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048

    @property
    def resolved_model(self) -> str:
        """Return the LiteLLM model string with provider prefix when needed."""
        if self.provider == "ollama" and not self.model.startswith("ollama/"):
            return f"ollama/{self.model}"
        if self.provider == "anthropic" and not self.model.startswith("anthropic/"):
            return self.model
        return self.model

    @property
    def resolved_api_base(self) -> str:
        """Return api_base, falling back to provider defaults."""
        if self.api_base:
            return self.api_base
        return PROVIDER_DEFAULTS.get(self.provider, {}).get("api_base", "")


@dataclass
class AppConfig:
    ai: AIConfig = field(default_factory=AIConfig)

    @classmethod
    def load(cls, path: Path | None = None) -> AppConfig:
        if path and path.exists():
            return cls._from_file(path)

        for candidate in DEFAULT_CONFIG_PATHS:
            if candidate.exists():
                return cls._from_file(candidate)

        return cls()

    @classmethod
    def _from_file(cls, path: Path) -> AppConfig:
        with open(path, "rb") as f:
            data = tomllib.load(f)

        ai_data = data.get("ai", {})
        provider = ai_data.get("provider", AIConfig.provider)
        defaults = PROVIDER_DEFAULTS.get(provider, {})
        ai = AIConfig(
            provider=provider,
            model=ai_data.get("model", defaults.get("model", AIConfig.model)),
            api_key=ai_data.get("api_key", AIConfig.api_key),
            api_base=ai_data.get("api_base", AIConfig.api_base),
            temperature=ai_data.get("temperature", AIConfig.temperature),
            max_tokens=ai_data.get("max_tokens", AIConfig.max_tokens),
        )
        return cls(ai=ai)
