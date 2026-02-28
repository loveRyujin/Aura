# Aura - TUI PDF Reader with AI Assistant

A modern terminal-based PDF reader built with [Textual](https://textual.textualize.io/), featuring an integrated AI assistant for summarizing, extracting key points, and translating content.

## Features

- **PDF Rendering** - Pages rendered as Markdown with headings, tables, and lists preserved
- **Page Navigation** - Arrow keys, `h`/`l`, or jump to specific page with `g`
- **Table of Contents** - Collapsible TOC panel extracted from PDF outline
- **Full-Text Search** - Search across all pages with `/`
- **AI Assistant** - Sidebar with quick commands and free-form chat
  - **Summarize** - AI-powered page summarization
  - **Key Points** - Extract bullet-point highlights
  - **Translate** - Translate between Chinese and English
- **File Browser** - Open any PDF with the built-in file dialog

## Requirements

- Python >= 3.13
- A terminal emulator (not an IDE console)

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd Aura

# Create virtual environment and install
uv venv --python 3.14
uv pip install --python .venv/bin/python -e .

# Or with pip
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

```bash
# Activate the virtual environment
source .venv/bin/activate

# Open a PDF file directly
python -m aura path/to/file.pdf

# Or launch and use the file browser
python -m aura
```

## Keybindings

| Key       | Action              |
|-----------|---------------------|
| `o`       | Open PDF file       |
| `t`       | Toggle TOC panel    |
| `a`       | Toggle AI sidebar   |
| `/`       | Search in PDF       |
| `g`       | Go to page          |
| `←` / `h` | Previous page      |
| `→` / `l` | Next page          |
| `q`       | Quit                |

## AI Configuration

Create an `aura.toml` in the project directory or `~/.config/aura/aura.toml`:

```toml
[ai]
model = "gpt-4o-mini"
api_key = "your-api-key"
api_base = ""           # optional, for custom endpoints
temperature = 0.7
max_tokens = 2048
```

Aura uses [LiteLLM](https://docs.litellm.ai/) under the hood, supporting 100+ LLM providers including OpenAI, Anthropic, Ollama, and more. Set the `model` field to any LiteLLM-compatible model string.

## Tech Stack

- **[Textual](https://textual.textualize.io/)** - Modern Python TUI framework
- **[PyMuPDF](https://pymupdf.readthedocs.io/)** - High-performance PDF parsing
- **[PyMuPDF4LLM](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/)** - PDF to Markdown conversion
- **[LiteLLM](https://docs.litellm.ai/)** - Unified LLM API gateway

## License

MIT
