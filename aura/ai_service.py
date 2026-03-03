"""AI service layer — structured prompts, context compression, slash commands."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum

from litellm import acompletion

from aura.config import AIConfig
from aura.session import ChatMessage, ChatSession

# ── Dynamic system prompt ────────────────────────────────────────

_SYSTEM_TEMPLATE = """\
You are Aura, an intelligent PDF reading assistant.
The user is reading a PDF document and may ask you to summarize, \
extract key points, translate, or answer questions about the content.
Be concise, accurate, and helpful.
When given page content as context, base your answers on that content.
{metadata}"""


@dataclass
class PDFMetadata:
    filename: str = ""
    page_count: int = 0
    toc_outline: str = ""
    current_section: str = ""
    current_page: int = 0


# ── Slash commands ───────────────────────────────────────────────

@dataclass
class SlashCommand:
    name: str
    description: str
    prompt_template: str


SLASH_COMMANDS: dict[str, SlashCommand] = {
    "summary": SlashCommand(
        name="summary",
        description="Summarize current page / section",
        prompt_template="Please provide a concise summary of the following content.",
    ),
    "keypoints": SlashCommand(
        name="keypoints",
        description="Extract key bullet points",
        prompt_template=(
            "Extract the key points from the following content as a bullet-point list."
        ),
    ),
    "translate": SlashCommand(
        name="translate",
        description="Translate content (default: zh↔en)",
        prompt_template=(
            "Translate the following content. "
            "If it is in Chinese, translate to English; if in English, translate to Chinese. "
            "{args}"
        ),
    ),
    "explain": SlashCommand(
        name="explain",
        description="Explain a concept in context",
        prompt_template="Explain the concept of '{args}' based on the current context.",
    ),
    "quiz": SlashCommand(
        name="quiz",
        description="Generate quiz questions",
        prompt_template=(
            "Generate 3-5 quiz questions (with answers) based on the following content."
        ),
    ),
}


def expand_slash_command(raw_input: str) -> str | None:
    """If *raw_input* starts with ``/cmd``, return expanded prompt; else None."""
    if not raw_input.startswith("/"):
        return None
    parts = raw_input.split(maxsplit=1)
    cmd_name = parts[0][1:]
    args = parts[1] if len(parts) > 1 else ""
    cmd = SLASH_COMMANDS.get(cmd_name)
    if not cmd:
        return None
    return cmd.prompt_template.replace("{args}", args).strip()


# ── Context scope ────────────────────────────────────────────────

class ContextScope(Enum):
    CURRENT_PAGE = "current_page"
    FULL_BOOK = "full_book"


# ── Compression prompt ───────────────────────────────────────────

_COMPRESS_PROMPT = (
    "Summarize the following conversation between a user and an AI assistant "
    "about a PDF document. Preserve key facts, decisions, and context needed "
    "to continue the conversation. Be concise (under 500 words).\n\n"
)

_RECENT_ROUNDS = 3


# ── AI Service ───────────────────────────────────────────────────

class AIService:
    """Manages AI conversations with structured prompts and compression."""

    def __init__(self, config: AIConfig) -> None:
        self._config = config
        self._book_context: str = ""
        self._metadata = PDFMetadata()
        self._session: ChatSession | None = None
        self._rounds_since_compress: int = 0

    # ── Session binding ──────────────────────────────────────────

    def bind_session(self, session: ChatSession) -> None:
        self._session = session
        self._rounds_since_compress = 0

    @property
    def history(self) -> list[ChatMessage]:
        return self._session.messages if self._session else []

    # ── PDF metadata ─────────────────────────────────────────────

    def set_pdf_metadata(
        self,
        filename: str,
        page_count: int,
        toc_outline: str,
    ) -> None:
        self._metadata = PDFMetadata(
            filename=filename,
            page_count=page_count,
            toc_outline=toc_outline,
        )

    def update_location(self, page: int, section: str) -> None:
        self._metadata.current_page = page
        self._metadata.current_section = section

    # ── Book context ─────────────────────────────────────────────

    def set_book_context(self, text: str) -> None:
        self._book_context = text

    @property
    def has_book_context(self) -> bool:
        return bool(self._book_context)

    def clear_all(self) -> None:
        self._book_context = ""
        self._metadata = PDFMetadata()
        self._session = None

    # ── Streaming response ───────────────────────────────────────

    async def stream_response(
        self,
        user_input: str,
        page_context: str = "",
        scope: ContextScope = ContextScope.CURRENT_PAGE,
    ) -> AsyncIterator[str]:
        """Stream an AI response token by token."""
        context = self._resolve_context(page_context, scope)
        messages = self._build_messages(user_input, context)

        if self._session:
            self._session.messages.append(
                ChatMessage(role="user", content=user_input)
            )

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

        assistant_msg = ChatMessage(
            role="assistant", content="".join(full_response)
        )
        if self._session:
            self._session.messages.append(assistant_msg)
            self._rounds_since_compress += 1

    # ── Context compression ──────────────────────────────────────

    async def maybe_compress(self) -> None:
        """Compress history if it exceeds the threshold."""
        if not self._session:
            return
        keep = _RECENT_ROUNDS * 2
        if len(self._session.messages) <= keep or self._rounds_since_compress < 5:
            return

        older = self._session.messages[:-keep]
        conversation_text = "\n".join(
            f"{m.role}: {m.content}" for m in older
        )

        try:
            kwargs: dict = {
                "model": self._config.resolved_model,
                "messages": [
                    {"role": "user", "content": _COMPRESS_PROMPT + conversation_text}
                ],
                "temperature": 0.3,
                "max_tokens": 1024,
                "stream": False,
            }
            if self._config.api_key:
                kwargs["api_key"] = self._config.api_key
            api_base = self._config.resolved_api_base
            if api_base:
                kwargs["api_base"] = api_base

            result = await acompletion(**kwargs)
            summary = result.choices[0].message.content or ""
            self._session.compressed_summary = summary
            self._session.messages = self._session.messages[-keep:]
            self._rounds_since_compress = 0
        except Exception:
            pass

    # ── Internal ─────────────────────────────────────────────────

    def _resolve_context(self, page_context: str, scope: ContextScope) -> str:
        if scope == ContextScope.FULL_BOOK and self._book_context:
            return self._book_context
        return page_context

    def _build_system_prompt(self) -> str:
        m = self._metadata
        parts: list[str] = []
        if m.filename:
            parts.append(f"\nBook: {m.filename} ({m.page_count} pages)")
        if m.toc_outline:
            parts.append(f"Table of Contents:\n{m.toc_outline}")
        metadata_block = "\n".join(parts)
        return _SYSTEM_TEMPLATE.format(metadata=metadata_block)

    def _build_messages(
        self, user_input: str, context: str
    ) -> list[ChatMessage]:
        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=self._build_system_prompt())
        ]

        if self._session and self._session.compressed_summary:
            messages.append(ChatMessage(
                role="system",
                content=f"Previous conversation summary:\n{self._session.compressed_summary}",
            ))

        keep = _RECENT_ROUNDS * 2
        recent = self.history[-keep:] if self.history else []
        messages.extend(recent)

        if context:
            truncated = context[:32000]
            m = self._metadata
            header = ""
            if m.current_section:
                header = (
                    f"Current location: {m.current_section} "
                    f"(p.{m.current_page + 1}/{m.page_count})\n\n"
                )
            label = (
                "Document content" if len(context) > 5000 else "Current page content"
            )
            messages.append(ChatMessage(
                role="system",
                content=f"{label}:\n{header}{truncated}",
            ))

        messages.append(ChatMessage(role="user", content=user_input))
        return messages
