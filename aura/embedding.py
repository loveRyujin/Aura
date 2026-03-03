"""Embedding service — thin wrapper around litellm.embedding()."""

from __future__ import annotations

from aura.config import EmbeddingConfig

from litellm import aembedding

_BATCH_SIZE = 50


class EmbeddingService:
    """Generates embeddings for text using OpenAI or Ollama via LiteLLM."""

    def __init__(self, config: EmbeddingConfig) -> None:
        self._config = config

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts, batching automatically."""
        all_embeddings: list[list[float]] = []
        for start in range(0, len(texts), _BATCH_SIZE):
            batch = texts[start : start + _BATCH_SIZE]
            response = await self._call(batch)
            all_embeddings.extend(
                item["embedding"] for item in response.data
            )
        return all_embeddings

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query string."""
        response = await self._call([text])
        return response.data[0]["embedding"]

    async def _call(self, inputs: list[str]):
        kwargs: dict = {
            "model": self._config.resolved_model,
            "input": inputs,
        }
        if self._config.api_key:
            kwargs["api_key"] = self._config.api_key
        api_base = self._config.resolved_api_base
        if api_base:
            kwargs["api_base"] = api_base
        if self._config.dimension:
            kwargs["dimensions"] = self._config.dimension
        return await aembedding(**kwargs)
