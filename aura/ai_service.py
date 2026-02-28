"""AI service layer wrapping LiteLLM for async streaming completions."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
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


class QuickCommand(Enum):
    SUMMARIZE = "summarize"
    KEY_POINTS = "key_points"
    TRANSLATE = "translate"


COMMAND_PROMPTS = {
    QuickCommand.SUMMARIZE: "Please summarize the following page content concisely:\n\n{content}",
    QuickCommand.KEY_POINTS: "Extract the key points from the following page content as a bullet list:\n\n{content}",
    QuickCommand.TRANSLATE: "Translate the following page content to Chinese (if already Chinese, translate to English):\n\n{content}",
}


@dataclass
class ChatMessage:
    role: str  # "user" | "assistant" | "system"
    content: str


class AIService:
    """Manages AI conversations with streaming support."""

    def __init__(self, config: AIConfig) -> None:
        self._config = config
        self._history: list[ChatMessage] = []

    @property
    def history(self) -> list[ChatMessage]:
        return self._history

    def clear_history(self) -> None:
        self._history.clear()

    async def stream_response(
        self,
        user_input: str,
        page_context: str = "",
    ) -> AsyncIterator[str]:
        """Stream an AI response token by token."""
        messages = self._build_messages(user_input, page_context)
        self._history.append(ChatMessage(role="user", content=user_input))

        kwargs: dict = {
            "model": self._config.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
            "stream": True,
        }
        if self._config.api_key:
            kwargs["api_key"] = self._config.api_key
        if self._config.api_base:
            kwargs["api_base"] = self._config.api_base

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

    async def quick_command(
        self,
        command: QuickCommand,
        page_content: str,
    ) -> AsyncIterator[str]:
        """Execute a predefined quick command with page content."""
        prompt = COMMAND_PROMPTS[command].format(content=page_content)
        async for token in self.stream_response(prompt, page_context=""):
            yield token

    def _build_messages(
        self, user_input: str, page_context: str
    ) -> list[ChatMessage]:
        messages = [ChatMessage(role="system", content=SYSTEM_PROMPT)]

        if page_context:
            context_msg = ChatMessage(
                role="system",
                content=f"Current page content:\n\n{page_context}",
            )
            messages.append(context_msg)

        for msg in self._history[-10:]:
            messages.append(msg)

        messages.append(ChatMessage(role="user", content=user_input))
        return messages
