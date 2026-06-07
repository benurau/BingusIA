# BingusIA

A self-hosted agentic AI programming assistant that connects to local or cloud LLMs (Ollama, OpenAI, Anthropic) to help with software engineering tasks. It can read/write files, search code, run shell commands, search the web, and maintain persistent memory across conversations.

## Features

- **Multi-provider:** Ollama (local), OpenAI, Anthropic, or any OpenAI-compatible API
- **File operations:** Read, write, edit files with diff display
- **Code search:** ripgrep-powered code search within a workspace
- **Web search:** DuckDuckGo search and page fetching
- **Persistent memory:** SQLite-backed semantic memory with embedding search
- **Rules/injections:** Extensible markdown-based rules with YAML frontmatter
- **GUI & REST API:** Optional tkinter GUI and FastAPI server
- **Cross-platform:** Windows, macOS, Linux

## Quick Start

```bash
pip install -e .
python main.py
```

Configure your provider and model in `bingus_ia_config.json`.
