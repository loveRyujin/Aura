"""AI service layer wrapping LiteLLM for async streaming completions."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum

from litellm import acompletion

from aura.config import AIConfig

SYSTEM_PROMPT = (
    "You are Aura, an intelligent PDF reading assistant. "
    "The user is reading a PDF document and may ask you to summarize, "
    "extract key points, translate, or answer questions about the content. "
    "Be concise, accurate, and helpful. "
    "When given page content as context, base your answers on that content."
)


class ContextScope(Enum):
    CURRENT_PAGE = "current_page"
    FULL_BOOK = "full_book"


@dataclass
class ChatMessage:
    role: str
    content: str


class AIService:
    """Manages AI conversations with streaming support."""

    def __init__(self, config: AIConfig) -> None:
        self._config = config
        self._history: list[ChatMessage] = []
        self._book_context: str = ""

    def set_book_context(self, text: str) -> None:
        self._book_context = text

    @property
    def has_book_context(self) -> bool:
        return bool(self._book_context)

    def clear_history(self) -> None:
        self._history.clear()

    def clear_all(self) -> None:
        self._history.clear()
        self._book_context = ""

    async def stream_response(
        self,
        user_input: str,
        page_context: str = "",
        scope: ContextScope = ContextScope.CURRENT_PAGE,
    ) -> AsyncIterator[str]:
        """Stream an AI response token by token."""
        context = self._resolve_context(page_context, scope)
        messages = self._build_messages(user_input, context)
        self._history.append(ChatMessage(role="user", content=user_input))

        kwargs: dict = {
            "model": self._config.resolved_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
            "stream": True,
        }
        if self._config.api_key:
            kwargs["api_key"] = self._config.api_key
        api_base = self._config.resolved_api_base
        if api_base:
            kwargs["api_base"] = api_base

        full_response: list[str] = []
        response = await acompletion(**kwargs)
        async for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                full_response.append(delta)
                yield delta

        self._history.append(
            ChatMessage(role="assistant", content="".join(full_response))
        )

    def _resolve_context(self, page_context: str, scope: ContextScope) -> str:
        if scope == ContextScope.FULL_BOOK and self._book_context:
            return self._book_context
        return page_context

    def _build_messages(
        self, user_input: str, context: str
    ) -> list[ChatMessage]:
        messages = [ChatMessage(role="system", content=SYSTEM_PROMPT)]

        if context:
            truncated = context[:32000] if len(context) > 32000 else context
            label = "Document content" if len(context) > 5000 else "Current page content"
            messages.append(ChatMessage(
                role="system",
                content=f"{label}:\n\n{truncated}",
            ))

        for msg in self._history[-10:]:
            messages.append(msg)

        messages.append(ChatMessage(role="user", content=user_input))
        return messages
