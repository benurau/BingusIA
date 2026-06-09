# BingusIA

A self-hosted agentic AI programming assistant that connects to local or cloud LLMs to autonomously perform software engineering tasks — file editing, code search, shell commands, web research, and more.

## Technologies

- **Python 3.11+** — Core language
- **LLM providers:** Ollama (local), OpenAI, Anthropic, OpenCode Zen
- **httpx** — Async HTTP for API calls & web fetching
- **FastAPI / uvicorn** — Optional REST API server
- **SQLite** — Semantic memory with embedding-based retrieval
- **tkinter** — Optional desktop GUI (terminal, editor, file explorer)
- **DuckDuckGo Search** — Web search integration
- **ripgrep** — Blazing-fast code search
- **pytest** — Test framework
- **PyYAML** — YAML frontmatter parsing for rules/injections
- **setuptools** — Build & packaging

## Quick Start

```bash
pip install -e .
python main.py
```

Configure your provider and model in `bingus_ia_config.json`.
