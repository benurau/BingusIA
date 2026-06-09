import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

from bingus_ia.core.config import save_config
from bingus_ia.core.reducer import ContextReducer
from bingus_ia.core.types import (
    Message, Role, ToolName, ToolResult, AgentConfig, Injection,
)
from bingus_ia.core.working_memory import WorkingMemory
from bingus_ia.files.reader import FileReader
from bingus_ia.files.editor import FileEditor
from bingus_ia.injections.registry import InjectionRegistry
from bingus_ia.injections.sandbox import InjectionSandbox
from bingus_ia.injections.web_summariser import WebSummariser
from bingus_ia.llm.base import BaseLLMClient
from bingus_ia.llm.factory import create_llm_client
from bingus_ia.memory.manager import MemoryManager
from bingus_ia.memory.blocks import MemoryBlocks
from bingus_ia.tools.web_search import WebSearch

SYSTEM_PROMPT = """You are Bingus, an AI programming assistant with file system access.

You work in short cycles.  Each turn decide ONE next action:
  - web_search / web_fetch / web_fetch_html — search and read web pages
  - read_file / search_code / list_dir — explore the codebase
  - edit_file / write_file / run_terminal — modify code or run commands
  - memory_lookup / memory_list / memory_block_* — manage persistent memory
  - create_rule / delete_rule / set_workspace — configure the assistant

Use function-calling for every action.  If unsupported, output JSON:
  {"name": "tool_name", "arguments": {...}}

Rules:
  - All paths must be within workspace: {{workspace_dir}}
  - If a tool fails twice, explain to the user and try a different approach.
  - Past exchanges are auto-saved.  Use memory_block_set for conventions.
  - For web content: web_search → pick URL → web_fetch (Markdown chunks).
  - Always share source URLs.  The answer must be based only on provided chunks.
  - After each tool result it is compressed into the [Working Memory] block above.
    Read it to recall what you discovered so far.
  - When you have enough information, stop making tool calls and write your
    final answer.  If the task needs code changes, produce the exact edits."""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read lines from a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to file"},
                    "offset": {"type": "integer", "description": "Line offset"},
                    "limit": {"type": "integer", "description": "Max lines"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace exact old_string with new_string in a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to file"},
                    "old_string": {"type": "string", "description": "Exact text to replace"},
                    "new_string": {"type": "string", "description": "Replacement text"},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file (creates/overwrites)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to file"},
                    "content": {"type": "string", "description": "File content"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List directory contents",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search code with ripgrep regex",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern"},
                    "include": {"type": "string", "description": "File glob filter"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_lookup",
            "description": "Search past conversations by text",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "description": "Max results"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_list",
            "description": "Show recent conversation history",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max entries"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_rule",
            "description": "Create a persistent rule/instruction applied to all future prompts",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Short name for the rule"},
                    "instruction": {"type": "string", "description": "The instruction to follow on every prompt"},
                    "trigger": {"type": "string", "description": "Optional trigger word (leave empty for always-active)"},
                },
                "required": ["name", "instruction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_rule",
            "description": "Delete a previously created rule by name",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the rule to delete"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_workspace",
            "description": "Change the workspace directory. All file operations will be relative to this new path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the new workspace directory"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_block_list",
            "description": "List all persistent memory blocks and their sizes",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_block_set",
            "description": "Overwrite a memory block entirely. Use for user preferences, project conventions, architecture decisions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Block name (persona, human, project, or custom)"},
                    "content": {"type": "string", "description": "New content for the block"},
                },
                "required": ["name", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_block_replace",
            "description": "Replace text inside an existing memory block",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Block name"},
                    "old_string": {"type": "string", "description": "Exact text to replace"},
                    "new_string": {"type": "string", "description": "Replacement text"},
                },
                "required": ["name", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information. Returns titles, URLs, and snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "num_results": {"type": "integer", "description": "Number of results (default 5)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Extract readable content from a URL using Readability/Trafilatura, convert to Markdown, and split into ~1k-token chunks. Use after web_search to get page details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to fetch"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch_html",
            "description": "Extract readable content from a URL using Readability/Trafilatura, output as structured XML (preserves tables, formatting), and split into ~1k-token chunks. Use after web_search for structured data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to fetch"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_terminal",
            "description": "Run a shell command. Use this to compile, run, test, or debug programs. Returns stdout, stderr, and exit code. Default timeout is 30s.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "workdir": {"type": "string", "description": "Working directory (defaults to workspace)"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)"},
                },
                "required": ["command"],
            },
        },
    },
]


class Agent:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.llm: BaseLLMClient = create_llm_client(config)
        self.reader = FileReader(config.workspace_dir)
        self.editor = FileEditor(config.workspace_dir)
        self.memory = MemoryManager(llm=self.llm, embedding_model=config.embedding_model) if config.memory_enabled else None
        self.blocks = MemoryBlocks(config.workspace_dir)
        self.web_search = WebSearch()
        self.injections = InjectionRegistry(config.injection_dir)
        self.prompt_dir = Path(config.prompt_dir).resolve()
        self._cached_extras: str = ""
        self._cached_extras_mtime: float = 0
        self.summariser = WebSummariser(self.llm)
        self.messages: list[Message] = []
        self.turn_count = 0
        self._workspace_display = config.workspace_dir
        self.wm = WorkingMemory()
        self.reducer = ContextReducer(llm=self.llm)
        self.current_file_path: str | None = None
        self.current_file_content: str = ""
        self.show_prompt = False
        self._original_context: list[Message] | None = None
        self._compress_attempts = 0

    def set_current_file(self, path: str | None, content: str = ""):
        self.current_file_path = path
        self.current_file_content = content

    def set_workspace(self, path: str) -> ToolResult:
        try:
            resolved = Path(path).resolve()
            if not resolved.is_dir():
                resolved.mkdir(parents=True, exist_ok=True)
            self.config.workspace_dir = str(resolved)
            self.reader.set_workspace(str(resolved))
            self.editor.set_workspace(str(resolved))
            self.blocks = MemoryBlocks(str(resolved))
            self._workspace_display = str(resolved)
            save_config(self.config)
            return ToolResult(
                ToolName.SET_WORKSPACE, True,
                f"Workspace changed to: {resolved}",
            )
        except PermissionError as e:
            return ToolResult(
                ToolName.SET_WORKSPACE, False, "",
                error=f"Permission denied: {e}",
            )
        except Exception as e:
            return ToolResult(
                ToolName.SET_WORKSPACE, False, "",
                error=f"Failed to set workspace: {e}",
            )

    async def rehearse(self) -> str:
        try:
            workspace_path = self.config.workspace_dir
            files_list = []
            try:
                for root, dirs, files in os.walk(workspace_path):
                    dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
                    for f in files:
                        if f.startswith("."):
                            continue
                        rel = os.path.relpath(os.path.join(root, f), workspace_path)
                        files_list.append(rel)
            except Exception:
                pass

            workspace_summary = "\n".join(sorted(files_list)[:150])

            msg = Message(role=Role.USER, content=(
                f"Analyze this project structure and tell me what type of "
                f"project it is (e.g., game engine, web framework, CLI tool, "
                f"data science library, etc.) in 1-3 words. Only respond with "
                f"the project type, nothing else.\n\n{workspace_summary}"
            ))
            classification_reply = await self.llm.chat([msg])
            project_type = classification_reply.content.strip()

            loop = asyncio.get_running_loop()
            search_result = await loop.run_in_executor(
                None, self.web_search.search,
                f"{project_type} development best practices architecture patterns", 5,
            )

            findings = f"Project identified as: {project_type}\n\n"
            if search_result.success:
                findings += "Web search results:\n" + search_result.output[:4000] + "\n\n"
                urls = re.findall(r'https?://[^\s\n]+', search_result.output)
                if urls:
                    fetch_result = await loop.run_in_executor(None, self.web_search.fetch, urls[0])
                    if fetch_result.success:
                        findings += f"Details from {urls[0]}:\n{fetch_result.output[:2000]}\n\n"

            summary_msg = Message(role=Role.USER, content=(
                f"Summarize the following information about {project_type} "
                f"development in 3-5 paragraphs. Focus on best practices, "
                f"common patterns, architecture decisions, and conventions "
                f"that would help an AI coding assistant be more effective "
                f"when working on this type of project.\n\n{findings[:6000]}"
            ))
            summary_reply = await self.llm.chat([summary_msg])
            summary = summary_reply.content.strip()

            safe_name = f"rehearse-{project_type.lower().replace(' ', '-').replace('/', '-')[:30]}"
            injection_text = (
                f"Project type: {project_type}\n\n"
                f"Rehearsal knowledge:\n{summary}\n\n"
                f"This injection was auto-generated by /rehearse. "
                f"It provides context about the project domain."
            )
            result = self.injections.create_rule(safe_name, injection_text, trigger="")
            return (
                f"Rehearsal complete.\n"
                f"  Project: {project_type}\n"
                f"  {result}\n"
                f"  Created injection with domain knowledge to improve task performance."
            )
        except Exception as e:
            return f"Rehearsal failed: {e}"

    async def run_terminal(self, command: str, workdir: str = "", timeout: int = 30) -> ToolResult:
        cwd = workdir or self.config.workspace_dir
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            out = stdout.decode(errors="replace")
            err = stderr.decode(errors="replace")

            result = out[:8000]
            if proc.returncode != 0:
                if err:
                    result = result + ("\n" + err[:4000]) if result else err[:4000]
                return ToolResult(
                    ToolName.RUN_TERMINAL, True,
                    output=result or "",
                    error=f"Exit code: {proc.returncode}",
                )

            if err:
                result = result + ("\n[stderr]\n" + err[:2000]) if result else err[:2000]
            return ToolResult(ToolName.RUN_TERMINAL, True, output=result[:10000])
        except asyncio.TimeoutError:
            return ToolResult(ToolName.RUN_TERMINAL, False, "", error=f"Command timed out after {timeout}s")
        except Exception as e:
            return ToolResult(ToolName.RUN_TERMINAL, False, "", error=str(e))

    async def run(self, user_input: str) -> str:
        self.turn_count = 0
        max_steps = min(self.config.max_turns, 10)

        for turn in range(max_steps):
            self.turn_count = turn + 1

            system = await self._build_system_prompt(user_input, self.wm)

            # Turn 1: full user query.  Later turns: short prompt to avoid
            # confusing the model with a repeated full instruction.
            prompt = user_input if turn == 0 else "Continue the task based on the context above."

            self.messages = [Message(role=Role.SYSTEM, content=system)]
            self.messages.append(Message(role=Role.USER, content=prompt))

            if self.show_prompt:
                print(f"  [plan] --- turn {self.turn_count}/{max_steps} ---", flush=True)
                print(f"  [plan] working memory:\n{self.wm.render()[:500]}", flush=True)
                print(f"  [plan] system: {len(system)} chars", flush=True)

            print(f"  [llm] calling {self.config.model}...", flush=True)
            reply = await self.llm.chat(
                messages=self.messages,
                tools=TOOL_DEFINITIONS,
            )

            tool_calls = list(reply.tool_calls)
            if not tool_calls and reply.content:
                parsed = self._parse_inline_tool_call(reply.content)
                if parsed:
                    tool_calls.append(parsed)
                    reply.content = ""

            if tool_calls:
                self.messages.append(reply)
                for tc in tool_calls:
                    source_key = f"step{self.turn_count}: {tc.get('function', {}).get('name', '?')}"
                    result = await self._execute_tool(tc)
                    if not result.success and result.error:
                        print(f"  [tool error] {result.error}", file=sys.stderr)

                    # Compress tool output into working memory
                    tc_name = tc.get("function", {}).get("name", "")
                    tool_args = tc.get("function", {}).get("arguments", {})
                    if isinstance(tool_args, str):
                        tool_args = json.loads(tool_args) if tool_args else {}
                    source_url = tool_args.get("url", "") if isinstance(tool_args, dict) else ""
                    facts = await self.reducer.reduce(
                        result.output or result.error or "",
                        query=user_input,
                    )
                    self.wm.add(source_key, facts, url=source_url)

                    # Put reduced result in messages (keep messages small)
                    reduced = "\n".join(f"  - {f}" for f in facts)
                    self.messages.append(Message(
                        role=Role.TOOL,
                        content=f"[{tc_name}] {reduced}\n[Result end]",
                        tool_call_id=tc.get("id", ""),
                    ))
                continue

            # LLM produced a final answer
            if reply.content:
                self.messages.append(reply)
                await self._store_memory(user_input, reply.content)
                self.blocks.remember_exchange(user_input, reply.content)
                return reply.content

            # Empty response fallback — compress history
            if self._compress_attempts < 3:
                self._compress_attempts += 1
                print(f"  [llm] empty response — compressing (attempt {self._compress_attempts}/3)", flush=True)
                await self._compress_context(user_input)
                continue
            print("  [llm] empty response after 3 compressions, giving up", flush=True)
            return "The model returned an empty response after multiple compression attempts."

        return "Agent reached maximum turn limit (10)."

    async def _build_system_prompt(self, user_input: str, wm: WorkingMemory | None = None) -> str:
        system = self.config.system_prompt or SYSTEM_PROMPT

        if self.current_file_path:
            filename = Path(self.current_file_path).name
            if self.current_file_content:
                line_count = self.current_file_content.count("\n") + 1
                lines = self.current_file_content.split("\n")[:40]
                snippet = "\n".join(lines)
                if line_count > 40:
                    snippet += "\n... (first 40 lines shown)"
            else:
                line_count = 0
                snippet = ""
            system += (
                f"\n\nOpen file in editor:\n"
                f"Path: {self.current_file_path}\n"
                f"Lines: {line_count}\n"
                f"Preview (first 40 lines):\n```\n{snippet}\n```\n"
            )

        ws_phrases = ("list all files", "workspace files", "directory structure",
                      "project files", "all files", "show tree", "file tree",
                      "list directory", "list files", "full tree", "folder structure")
        user_lower = user_input.lower()
        include_listing = any(p in user_lower for p in ws_phrases)

        if include_listing:
            workspace_path = self.config.workspace_dir
            if workspace_path and Path(workspace_path).is_dir():
                try:
                    all_files = []
                    for root, dirs, files in os.walk(workspace_path):
                        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
                        for f in files:
                            if f.startswith("."):
                                continue
                            full = os.path.join(root, f)
                            all_files.append(os.path.relpath(full, workspace_path))
                    if all_files:
                        total = len(all_files)
                        shown = sorted(all_files)[:50]
                        listing = "\n".join(f"  {f}" for f in shown)
                        if total > 50:
                            listing += f"\n  ... and {total - 50} more files"
                        system += f"\n\nWorkspace ({total} files, showing first 50):\n{listing}"
                except Exception:
                    pass

        matched = self.injections.match(user_input)
        if matched:
            context = {
                "workspace_dir": self.config.workspace_dir,
                "current_file": "",
                "user_input": user_input,
                "model_name": self.config.model,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for inj in matched:
                is_valid, err = InjectionSandbox.validate(inj)
                if is_valid:
                    rendered = InjectionSandbox.render(inj, context)
                    injection_block = f"\n\n[Injection: {inj.name}]\n{rendered[:2000]}"

                    if inj.urls:
                        summaries = await self.summariser.summarise_urls(inj)
                        for s in summaries:
                            injection_block += f"\n[Web Summary: {s['url']}]\n{s['summary'][:1000]}"
                            await self._store_memory(f"Injection URL: {s['url']}", s["summary"])

                    system = f"{system}{injection_block}"
                else:
                    print(f"Injection '{inj.name}' blocked: {err}")

        blocks_rendered = self.blocks.render_for_prompt()
        if blocks_rendered:
            system = f"{system}\n\nPersistent Memory:\n{blocks_rendered}"

        if self.memory:
            memories = await self.memory.recall(user_input, limit=3)
            if memories:
                history = "\n".join(
                    f"Past: {m.prompt[:100]} -> {m.response[:150]}"
                    for m in memories
                )
                system = f"{system}\n\nRelevant past context:\n{history}"

        if self.prompt_dir.is_dir():
            md_files = sorted(self.prompt_dir.glob("*.md"))
            if md_files:
                latest_mtime = max(f.stat().st_mtime for f in md_files)
                if latest_mtime != self._cached_extras_mtime or not self._cached_extras:
                    extras = []
                    for f in md_files:
                        try:
                            content = f.read_text(encoding="utf-8").strip()
                            if content:
                                extras.append(f"--- {f.stem} ---\n{content[:500]}")
                        except Exception:
                            pass
                    self._cached_extras = "\n\n".join(extras) if extras else ""
                    self._cached_extras_mtime = latest_mtime
                if self._cached_extras:
                    system = f"{system}\n\nPrompt Extras:\n{self._cached_extras}"

        if wm:
            wm_text = wm.render()
            if wm_text:
                system = f"{system}\n\n{wm_text}"

        return system

    async def _compress_context(self, user_input: str) -> None:
        parts = []
        for m in self.messages:
            role = m.role.value
            content = m.content or ""
            extra = ""
            if m.tool_calls:
                extra = f"\n[tool_calls]\n{json.dumps(m.tool_calls, default=str)}"
            if m.tool_call_id:
                extra += f"\n[tool_call_id: {m.tool_call_id}]"
            parts.append(f"[{role}]\n{content}{extra}")
        full_text = "\n\n---\n\n".join(parts)

        chunk_size = 4000
        chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]

        if len(chunks) <= 1:
            truncated = full_text[:6000]
            self.messages = [
                Message(role=Role.SYSTEM, content=f"[Truncated context]\n\n{truncated}"),
                Message(role=Role.USER, content=user_input),
            ]
            return

        print(f"  [compress] splitting {len(full_text)} chars into {len(chunks)} chunks", flush=True)
        accumulated = ""
        for i, chunk in enumerate(chunks):
            prefix = f"Previous summary:\n{accumulated}\n\n" if accumulated else ""
            prompt = (
                f"{prefix}"
                f"Summarize this technical context chunk ({i+1}/{len(chunks)}). "
                f"Priority: preserve code, file paths, errors, "
                f"and specs verbatim. Omit filler.\n\n{chunk}"
            )
            try:
                msg = Message(role=Role.USER, content=prompt)
                reply = await self.llm.chat([msg])
                accumulated += (reply.content or "") + "\n"
            except Exception:
                accumulated += chunk + "\n"
            print(f"  [compress] chunk {i+1}/{len(chunks)} done ({len(accumulated)} chars total)", flush=True)

        system = f"[Compressed context]\n\n{accumulated.strip()}"
        self.messages = [
            Message(role=Role.SYSTEM, content=system),
            Message(role=Role.USER, content=user_input),
        ]

    def _parse_inline_tool_call(self, content: str) -> dict | None:
        lines = content.strip().splitlines()
        non_empty = [l for l in lines if l.strip()]
        if len(non_empty) > 6:
            return None

        json_block = content.strip()
        json_block = re.sub(r"^```(?:json)?\s*", "", json_block)
        json_block = re.sub(r"\s*```$", "", json_block)

        try:
            data = json.loads(json_block)
        except json.JSONDecodeError:
            return None

        if not isinstance(data, dict):
            return None

        func = data.get("function", {})
        name = (
            data.get("name")
            or data.get("tool_name")
            or func.get("name", "")
        )
        raw_args = (
            data.get("arguments")
            or data.get("params")
            or data.get("parameters")
            or func.get("arguments")
            or func.get("parameters")
            or {}
        )
        if isinstance(raw_args, str):
            try:
                raw_args = json.loads(raw_args)
            except json.JSONDecodeError:
                return None

        if name:
            return {
                "function": {
                    "name": name,
                    "arguments": raw_args,
                }
            }
        return None

    def _summarize_args(self, name: str, args: dict) -> str:
        if name in ("web_search",):
            return f'query="{args.get("query", "")}"'
        if name in ("web_fetch", "web_fetch_html"):
            return f'url="{args.get("url", "")}"'
        if name in ("read_file", "edit_file", "write_file"):
            return f'path="{args.get("path", "")}"'
        if name == "run_terminal":
            cmd = args.get("command", "")
            return f'command="{cmd[:80]}{"..." if len(cmd) > 80 else ""}"'
        if name in ("memory_lookup", "search_code"):
            return f'query="{args.get("query", "")}"'
        return ""

    async def _execute_tool(self, tc: dict) -> ToolResult:
        name = tc.get("function", {}).get("name", "")
        args_raw = tc.get("function", {}).get("arguments", "{}")
        args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw

        summary = self._summarize_args(name, args)
        if summary:
            print(f"  [tool] {name}({summary})", flush=True)
        else:
            print(f"  [tool] {name}", flush=True)

        tool_map = {
            "read_file": lambda: self.reader.read_file(args.get("path", ""), args.get("offset", 0), args.get("limit")),
            "edit_file": lambda: self.editor.edit_file(args.get("path", ""), args.get("old_string", ""), args.get("new_string", "")),
            "write_file": lambda: self.editor.write_file(args.get("path", ""), args.get("content", "")),
            "list_dir": lambda: self.reader.list_dir(args.get("path", ".")),
            "search_code": lambda: self.reader.search_code(args.get("pattern", ""), args.get("include")),
            "memory_lookup": lambda: self.memory.lookup(args.get("query", ""), args.get("limit", 5)) if self.memory else ToolResult(ToolName.MEMORY_LOOKUP, False, "", error="Memory disabled"),
            "memory_list": lambda: self.memory.get_recent(args.get("limit", 10)) if self.memory else ToolResult(ToolName.MEMORY_LOOKUP, False, "", error="Memory disabled"),
            "create_rule": lambda: ToolResult(
                ToolName.RUN_COMMAND, True,
                self.injections.create_rule(args.get("name", ""), args.get("instruction", ""), args.get("trigger", "")),
            ),
            "delete_rule": lambda: ToolResult(
                ToolName.RUN_COMMAND, True,
                self.injections.delete_rule(args.get("name", "")),
            ),
            "set_workspace": lambda: self.set_workspace(args.get("path", "")),
            "memory_block_list": lambda: self.blocks.list_blocks(),
            "memory_block_set": lambda: self.blocks.set_block(args.get("name", ""), args.get("content", "")),
            "memory_block_replace": lambda: self.blocks.replace_in_block(args.get("name", ""), args.get("old_string", ""), args.get("new_string", "")),
            "web_search": lambda: self.web_search.search(args.get("query", ""), args.get("num_results", 5)),
            "web_fetch": lambda: self.web_search.fetch(args.get("url", "")),
            "web_fetch_html": lambda: self.web_search.fetch_html(args.get("url", "")),
            "run_terminal": lambda: self.run_terminal(args.get("command", ""), args.get("workdir", ""), args.get("timeout", 30)),
        }

        handler = tool_map.get(name)
        if not handler:
            return ToolResult(ToolName.RUN_COMMAND, False, "", error=f"Unknown tool: {name}")

        try:
            result = handler()
            if asyncio.iscoroutine(result):
                result = await result
            return result
        except PermissionError as e:
            return ToolResult(
                ToolName(name),
                False, "",
                error=f"[Permission Denied] Tool '{name}' could not access the file system:\n  {e}\n\n"
                      f"Suggestions:\n"
                      f"  - Make sure the file/folder is not read-only\n"
                      f"  - Close any programs (editor, antivirus) that may have locked the file\n"
                      f"  - Try a different location (e.g. Desktop or Documents)",
            )
        except FileNotFoundError as e:
            return ToolResult(
                ToolName(name),
                False, "",
                error=f"[File Not Found] Tool '{name}': {e}",
            )
        except Exception as e:
            return ToolResult(
                ToolName(name),
                False, "",
                error=f"[Tool Error] '{name}' failed: {e}\nArgs: {json.dumps(args, default=str)[:500]}",
            )

    async def _store_memory(self, prompt: str, response: str) -> None:
        if not self.memory:
            return
        try:
            await self.memory.remember(prompt, response, {"model": self.config.model})
        except Exception:
            pass

    async def close(self):
        self.summariser.close()
        self.web_search.close()
        await self.llm.close()
