# Aura - TUI PDF Reader with AI Assistant

A modern terminal-based PDF reader built with [Textual](https://textual.textualize.io/), featuring an integrated AI assistant for analyzing and summarizing book content.

## Features

- **PDF Rendering** - Text mode (Markdown) and image mode (Sixel / Kitty TGP / Halfcell)
- **Two Scroll Modes** - Paginated (classic single-page) and continuous scrolling, toggle with `c`
- **Smooth Navigation** - Debounced page flipping with adjacent-page prefetch for zero-lag reading
- **Table of Contents** - Collapsible, resizable TOC panel extracted from PDF outline
- **Full-Text Search** - Search across all pages with `/`
- **AI Assistant** - Keyboard-driven chat sidebar supporting page-level and whole-book analysis
- **Multi-LLM Support** - OpenAI, Anthropic, Ollama, and 100+ providers via LiteLLM
- **File Browser** - Open any PDF with the built-in file dialog
- **Standalone Build** - Package as a single executable with PyInstaller

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
source .venv/bin/activate

# Method 1: CLI command (after pip install -e .)
aura path/to/file.pdf

# Method 2: Python module
python -m aura path/to/file.pdf

# Launch without file (use 'o' to open file browser)
aura
```

## Build Standalone Executable

Package Aura as a single binary that runs without Python installed:

```bash
# Install build dependency
pip install pyinstaller
# Or: pip install -e ".[build]"

# Build the executable
python build.py

# The binary is at dist/aura
./dist/aura path/to/file.pdf
```

## Keybindings

| Key        | Action                             |
|------------|------------------------------------|
| `o`        | Open PDF file                      |
| `t`        | Toggle TOC panel                   |
| `a`        | Toggle AI sidebar                  |
| `s`        | Toggle AI scope (page / book)      |
| `v`        | Toggle view mode (text / image)    |
| `c`        | Toggle scroll mode (page / scroll) |
| `/`        | Search in PDF                      |
| `g`        | Go to page                         |
| `←` / `h`  | Previous page                      |
| `→` / `l`  | Next page                          |
| `q`        | Quit                               |

## Image Rendering

Aura supports terminal graphics protocols for higher-quality PDF rendering in image mode (`v`):

| Protocol  | Terminals                                |
|-----------|------------------------------------------|
| Kitty TGP | Kitty                                    |
| Sixel     | WezTerm, Windows Terminal 1.22+, iTerm2  |
| Halfcell  | Any terminal (fallback)                  |

The renderer is auto-detected. To force a specific one, set the `AURA_RENDERER` environment variable:

```bash
AURA_RENDERER=sixel aura book.pdf
AURA_RENDERER=tgp aura book.pdf
AURA_RENDERER=halfcell aura book.pdf
```

## AI Configuration

Create an `aura.toml` in the project directory or `~/.config/aura/aura.toml`:

**OpenAI (default):**

```toml
[ai]
provider = "openai"
model = "gpt-4o-mini"
api_key = "sk-..."
```

**Ollama (local, no API key needed):**

```toml
[ai]
provider = "ollama"
model = "llama3"        # or qwen2, mistral, gemma2, etc.
```

**Anthropic:**

```toml
[ai]
provider = "anthropic"
model = "claude-3-haiku-20240307"
api_key = "sk-ant-..."
```

The `provider` field controls how the model string is resolved. For Ollama, `api_base` defaults to `http://localhost:11434` and the `ollama/` prefix is auto-added. See `config.example.toml` for all options.

Aura uses [LiteLLM](https://docs.litellm.ai/) under the hood, supporting 100+ LLM providers.

## Tech Stack

- **[Textual](https://textual.textualize.io/)** - Modern Python TUI framework
- **[PyMuPDF](https://pymupdf.readthedocs.io/)** - High-performance PDF parsing
- **[PyMuPDF4LLM](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/)** - PDF to Markdown conversion
- **[textual-image](https://github.com/lnqs/textual-image)** - Terminal graphics protocol support (Sixel / Kitty TGP / Halfcell)
- **[LiteLLM](https://docs.litellm.ai/)** - Unified LLM API gateway

## License

MIT
