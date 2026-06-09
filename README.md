# BingusIA

A self-hosted agentic AI programming assistant that connects to local or cloud LLMs to autonomously perform software engineering tasks — file editing, code search, shell commands, web research, and more.

## Features

- **Multi-provider LLM support:** Ollama (local), OpenAI, Anthropic, OpenCode Zen
- **Desktop GUI:** Terminal, syntax-highlighted editor, and file explorer
- **File operations:** Read, write, edit files with diff display
- **Code search:** ripgrep-powered code search within a workspace
- **Web search:** DuckDuckGo search and page fetching
- **Persistent memory:** SQLite-backed semantic memory with embedding search
- **Rules/injections:** Extensible markdown-based rules with YAML frontmatter
- **REST API:** Optional FastAPI server (`pip install bingus-ia[server]`)
- **Benchmark suite:** 30 automated tasks to measure agent performance across changes (`python benchmark/run.py`)

## Technologies

- **Python 3.11+** — Core language
- **LLM providers:** Ollama (local), OpenAI, Anthropic, OpenCode Zen
- **httpx** — Async HTTP for API calls & web fetching
- **FastAPI / uvicorn** — Optional REST API server
- **SQLite** — Semantic memory with embedding-based retrieval
- **tkinter** — Desktop GUI (terminal, editor, file explorer)
- **DuckDuckGo Search** — Web search integration
- **ripgrep** — Blazing-fast code search
- **pytest** — Test framework + benchmark evaluation
- **PyYAML** — YAML frontmatter parsing for rules/injections
- **setuptools** — Build & packaging

## Quick Start

```bash
pip install -e .
python main.py
```

Configure your provider and model in `bingus_ia_config.json`.

## Benchmark

Run 30 automated coding tasks to measure agent performance:

```bash
python benchmark/run.py --provider ollama --model <model>
python benchmark/run.py --provider openai --model gpt-4 --tasks 1-10
python benchmark/run.py --help
```
