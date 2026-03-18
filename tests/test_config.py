"""Tests for config.py - Configuration management."""

import os
import tempfile
from pathlib import Path

import pytest

from aura.config import (
    AIConfig,
    AppConfig,
    EmbeddingConfig,
    PROVIDER_DEFAULTS,
    EMBEDDING_PROVIDER_DEFAULTS,
)


class TestAIConfig:
    """Tests for the AIConfig dataclass."""

    def test_defaults(self):
        config = AIConfig()
        assert config.provider == "openai"
        assert config.model == "gpt-4o-mini"
        assert config.api_key == ""
        assert config.api_base == ""
        assert config.temperature == 0.7
        assert config.max_tokens == 2048

    def test_custom_values(self):
        config = AIConfig(
            provider="anthropic",
            model="claude-3-sonnet",
            api_key="sk-test",
            api_base="https://api.anthropic.com",
            temperature=0.5,
            max_tokens=4096,
        )
        assert config.provider == "anthropic"
        assert config.model == "claude-3-sonnet"
        assert config.api_key == "sk-test"
        assert config.api_base == "https://api.anthropic.com"
        assert config.temperature == 0.5
        assert config.max_tokens == 4096


class TestAIConfigResolved:
    """Tests for resolved properties."""

    def test_resolved_model_openai(self):
        config = AIConfig(provider="openai", model="gpt-4o")
        assert config.resolved_model == "gpt-4o"

    def test_resolved_model_ollama_adds_prefix(self):
        config = AIConfig(provider="ollama", model="llama3")
        assert config.resolved_model == "ollama/llama3"

    def test_resolved_model_ollama_keeps_existing_prefix(self):
        config = AIConfig(provider="ollama", model="ollama/llama3")
        assert config.resolved_model == "ollama/llama3"

    def test_resolved_model_anthropic(self):
        config = AIConfig(provider="anthropic", model="claude-3-haiku")
        assert config.resolved_model == "claude-3-haiku"

    def test_resolved_api_base_custom(self):
        config = AIConfig(api_base="https://custom.api.com")
        assert config.resolved_api_base == "https://custom.api.com"

    def test_resolved_api_base_ollama_default(self):
        config = AIConfig(provider="ollama")
        assert config.resolved_api_base == "http://localhost:11434"

    def test_resolved_api_base_openai_default(self):
        config = AIConfig(provider="openai")
        assert config.resolved_api_base == ""

    def test_resolved_api_base_anthropic_default(self):
        config = AIConfig(provider="anthropic")
        assert config.resolved_api_base == ""


class TestEmbeddingConfig:
    """Tests for the EmbeddingConfig dataclass."""

    def test_defaults(self):
        config = EmbeddingConfig()
        assert config.provider == "openai"
        assert config.model == "text-embedding-3-small"
        assert config.api_key == ""
        assert config.api_base == ""
        assert config.dimension == 512
        assert config.chunk_size == 1024
        assert config.chunk_overlap == 128
        assert config.top_k == 5


class TestEmbeddingConfigResolved:
    """Tests for EmbeddingConfig resolved properties."""

    def test_resolved_model_openai(self):
        config = EmbeddingConfig(provider="openai", model="text-embedding-3-small")
        assert config.resolved_model == "text-embedding-3-small"

    def test_resolved_model_ollama_adds_prefix(self):
        config = EmbeddingConfig(provider="ollama", model="nomic-embed-text")
        assert config.resolved_model == "ollama/nomic-embed-text"

    def test_resolved_api_base_custom(self):
        config = EmbeddingConfig(api_base="https://custom.api.com")
        assert config.resolved_api_base == "https://custom.api.com"

    def test_resolved_api_base_ollama_default(self):
        config = EmbeddingConfig(provider="ollama")
        assert config.resolved_api_base == "http://localhost:11434"


class TestAppConfig:
    """Tests for the AppConfig class."""

    def test_defaults(self):
        config = AppConfig()
        assert isinstance(config.ai, AIConfig)
        assert isinstance(config.embedding, EmbeddingConfig)

    def test_custom_nested_configs(self):
        ai = AIConfig(provider="ollama", model="llama3")
        embedding = EmbeddingConfig(provider="ollama", model="nomic-embed-text")
        config = AppConfig(ai=ai, embedding=embedding)

        assert config.ai.provider == "ollama"
        assert config.embedding.provider == "ollama"


class TestAppConfigLoad:
    """Tests for AppConfig.load() method."""

    def test_load_returns_defaults_when_no_file(self, monkeypatch):
        # Make sure no config file exists
        monkeypatch.setattr("aura.config.DEFAULT_CONFIG_PATHS", [])
        config = AppConfig.load()
        assert config.ai.provider == "openai"
        assert config.embedding.provider == "openai"

    def test_load_from_specific_path(self):
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".toml", delete=False
        ) as f:
            f.write(
                b"""
[ai]
provider = "ollama"
model = "llama3"

[embedding]
provider = "ollama"
model = "nomic-embed-text"
"""
            )
            f.flush()

            config = AppConfig.load(path=Path(f.name))
            assert config.ai.provider == "ollama"
            assert config.ai.model == "llama3"
            assert config.embedding.provider == "ollama"
            assert config.embedding.model == "nomic-embed-text"

            os.unlink(f.name)

    def test_load_uses_defaults_for_missing_fields(self):
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".toml", delete=False
        ) as f:
            f.write(b"[ai]\nprovider = 'anthropic'\n")
            f.flush()

            config = AppConfig.load(path=Path(f.name))
            # Should use provider-specific defaults for missing fields
            assert config.ai.provider == "anthropic"
            assert config.ai.model == "claude-3-haiku-20240307"  # Anthropic default
            assert config.ai.temperature == 0.7  # Global default

            os.unlink(f.name)

    def test_load_ai_temperature(self):
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".toml", delete=False
        ) as f:
            f.write(b"[ai]\ntemperature = 0.3\n")
            f.flush()

            config = AppConfig.load(path=Path(f.name))
            assert config.ai.temperature == 0.3

            os.unlink(f.name)

    def test_load_embedding_dimension(self):
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".toml", delete=False
        ) as f:
            f.write(b"[embedding]\ndimension = 768\n")
            f.flush()

            config = AppConfig.load(path=Path(f.name))
            assert config.embedding.dimension == 768

            os.unlink(f.name)
