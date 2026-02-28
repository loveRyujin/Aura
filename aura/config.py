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


@dataclass
class AIConfig:
    model: str = "gpt-4o-mini"
    api_key: str = ""
    api_base: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048


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
        ai = AIConfig(
            model=ai_data.get("model", AIConfig.model),
            api_key=ai_data.get("api_key", AIConfig.api_key),
            api_base=ai_data.get("api_base", AIConfig.api_base),
            temperature=ai_data.get("temperature", AIConfig.temperature),
            max_tokens=ai_data.get("max_tokens", AIConfig.max_tokens),
        )
        return cls(ai=ai)
