# BingusIA

A self-hosted code editing agent. Open a file in the GUI, type a request, and the agent edits it via AST-aware context extraction and unified diff patches.

## How it works

```
User request
   ↓
AST parse file → find relevant function/class
   ↓
Extract target + ±50 surrounding lines
   ↓
Send to LLM as a single-shot prompt
   ↓
Parse unified diff from response
   ↓
Apply patch to file
```

- **AST-based region locator** (Python `ast`): finds the right function, method, or insertion point by matching your query against names, docstrings, and keywords.
- **Keyword-search fallback**: if the file has syntax errors, falls back to line-by-line keyword scoring.
- **Single-turn**: no tool-calling loop, no function call registry, no working memory. One LLM call → one diff → one patch.
- **Unified diff**: the model outputs a standard `diff -u` patch; the editor parses and applies it.

## Features

- **Multi-provider LLM:** Ollama (local), OpenAI, Anthropic, OpenCode Zen
- **Desktop GUI:** tkinter — file explorer, syntax-highlighted editor, prompt terminal
- **File operations:** read, write, edit with diff display (all on the currently open file only)
- **`/showprompt`:** toggle full prompt/reply display for debugging

## Quick Start

```bash
pip install -e .
python gui.py
```

Configure your provider and model in `bingus_ia_config.json`:

```json
{
  "provider": "ollama",
  "model": "gemma4:e4b",
  "workspace_dir": ".",
  "max_turns": 10
}
```

Or via CLI:

```bash
python main.py "add a function that prints prime numbers"
```

(CLI mode requires `current_file_path` to be set — use the GUI for now.)

## Project layout

```
bingus_ia/
├── __main__.py         # CLI entry point
├── core/
│   ├── agent.py        # Agent: build prompt → call LLM → apply diff
│   ├── config.py       # Config load/save
│   ├── types.py        # Enums, Message, ToolResult, AgentConfig
│   ├── reducer.py      # (unused, kept for reference)
│   └── working_memory.py  # (unused, kept for reference)
├── files/
│   ├── region.py       # AST-based region locator + keyword fallback
│   ├── editor.py       # edit_file, write_file, apply_patch
│   ├── reader.py       # read_file
│   └── diff_display.py # Pretty-print unified diffs
├── gui/
│   └── app.py          # tkinter GUI (file explorer + editor + prompt terminal)
└── llm/
    ├── base.py         # Abstract LLM client
    ├── factory.py      # create_llm_client()
    ├── ollama_client.py
    ├── openai_client.py
    └── anthropic_client.py
```

## Technologies

- **Python 3.11+**
- **LLM providers:** Ollama, OpenAI, Anthropic, OpenCode Zen
- **httpx** — Async HTTP for API calls
- **tkinter** — Desktop GUI
- **setuptools** — Build & packaging
