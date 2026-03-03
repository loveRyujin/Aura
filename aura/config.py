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

EMBEDDING_PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "ollama": {"api_base": "http://localhost:11434", "model": "nomic-embed-text"},
    "openai": {"api_base": "", "model": "text-embedding-3-small"},
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
class EmbeddingConfig:
    provider: str = "openai"
    model: str = "text-embedding-3-small"
    api_key: str = ""
    api_base: str = ""
    dimension: int = 512
    chunk_size: int = 1024
    chunk_overlap: int = 128
    top_k: int = 5

    @property
    def resolved_model(self) -> str:
        if self.provider == "ollama" and not self.model.startswith("ollama/"):
            return f"ollama/{self.model}"
        return self.model

    @property
    def resolved_api_base(self) -> str:
        if self.api_base:
            return self.api_base
        return EMBEDDING_PROVIDER_DEFAULTS.get(self.provider, {}).get("api_base", "")


@dataclass
class AppConfig:
    ai: AIConfig = field(default_factory=AIConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)

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

        emb_data = data.get("embedding", {})
        emb_provider = emb_data.get("provider", EmbeddingConfig.provider)
        emb_defaults = EMBEDDING_PROVIDER_DEFAULTS.get(emb_provider, {})
        embedding = EmbeddingConfig(
            provider=emb_provider,
            model=emb_data.get(
                "model", emb_defaults.get("model", EmbeddingConfig.model)
            ),
            api_key=emb_data.get("api_key", EmbeddingConfig.api_key),
            api_base=emb_data.get("api_base", EmbeddingConfig.api_base),
            dimension=emb_data.get("dimension", EmbeddingConfig.dimension),
            chunk_size=emb_data.get("chunk_size", EmbeddingConfig.chunk_size),
            chunk_overlap=emb_data.get("chunk_overlap", EmbeddingConfig.chunk_overlap),
            top_k=emb_data.get("top_k", EmbeddingConfig.top_k),
        )

        return cls(ai=ai, embedding=embedding)
