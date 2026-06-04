import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Optional

from bingus_ia.core.types import (
    Message, Role, ToolName, ToolResult, AgentConfig, Injection,
)
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
You can read and edit files in the workspace. You have memory of past conversations.

Available tools:
- write_file(path, content) - Use this to CREATE a new file or OVERWRITE an existing one
- edit_file(path, old_string, new_string) - Use this to MODIFY an existing file by replacing exact text
- read_file(path, offset?, limit?) - Read a file's contents
- list_dir(path?) - List directory contents
- search_code(pattern, include?) - Search code with ripgrep
- memory_lookup(query, limit?) - Search past conversations
- memory_list(limit?) - Show recent conversation history
- create_rule(name, instruction, trigger?) - Create a persistent rule applied to all future prompts
- delete_rule(name) - Remove a persistent rule
- memory_block_list() - List persistent memory blocks (persona, human, project)
- memory_block_set(name, content) - Overwrite a memory block entirely
- memory_block_replace(name, old_string, new_string) - Replace text inside a memory block
- web_search(query) - Search the web, returns titles/URLs/snippets
- web_fetch(url) - Fetch full content from a URL, returns the page text
- set_workspace(path) - Change the workspace directory
- run_terminal(command, workdir?, timeout?) - Run a shell command and return its output (use for running/test programs)

IMPORTANT RULES FOR TOOL SELECTION:
- To CREATE a new file, ALWAYS use write_file, NOT edit_file
- To OVERWRITE an existing file entirely, ALWAYS use write_file
- edit_file is ONLY for making precise replacements inside an existing file
- If you use edit_file with an empty old_string on a file that doesn't exist, it will create the file
- All file paths must be relative to the workspace directory or within it: {{workspace_dir}}
- Writing or reading outside this directory will fail. Tell the user and suggest moving the file.

AUTOMATIC MEMORY:
- Every conversation exchange is automatically saved as an "exchange" block
- Old exchanges are evicted (oldest first) when the 300 token budget is exceeded
- You can also manually save important info with memory_block_set/memory_block_replace
- Use memory_block_set(name="project", content="...") for project conventions
- Use memory_block_set(name="persona", content="...") for behavioral preferences
- Custom blocks are automatically deleted if they don't fit in the budget (keep them small)

WEB SEARCH WORKFLOW:
- Use web_search(query) to find information online — returns titles, URLs, and short snippets
- Use web_fetch(url) to get the full content of a specific page
- Typical flow: web_search("hamburger recipe") → pick best URL → web_fetch(url) → present the recipe to the user
- Always share the source URL when presenting fetched content

When a tool returns an error, explain it clearly to the user.
After using a tool, wait for the result before continuing.
Think step by step. Read files before editing them.

When you need to call a tool, use the function-calling mechanism.
If your model does not support function calling, output a single JSON object:
{"name": "write_file", "arguments": {"path": "test.txt", "content": "hello"}}
Do not wrap it in markdown or add any other text."""

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
            "description": "Fetch and extract the full text content from a URL. Use after web_search to get page details.",
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
        self.summariser = WebSummariser(self.llm)
        self.messages: list[Message] = []
        self.turn_count = 0
        self._workspace_display = config.workspace_dir

    def set_workspace(self, path: str) -> ToolResult:
        resolved = Path(path).resolve()
        if not resolved.is_dir():
            resolved.mkdir(parents=True, exist_ok=True)
        self.config.workspace_dir = str(resolved)
        self.reader.set_workspace(str(resolved))
        self.editor.set_workspace(str(resolved))
        self.blocks = MemoryBlocks(str(resolved))
        self._workspace_display = str(resolved)
        return ToolResult(
            ToolName.SET_WORKSPACE, True,
            f"Workspace changed to: {resolved}",
        )

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

            result = out[:4000]
            if proc.returncode != 0:
                if err:
                    result = result + ("\n" + err[:2000]) if result else err[:2000]
                return ToolResult(
                    ToolName.RUN_TERMINAL, True,
                    output=result or "",
                    error=f"Exit code: {proc.returncode}",
                )

            if err:
                result = result + ("\n[stderr]\n" + err[:1000]) if result else err[:1000]
            return ToolResult(ToolName.RUN_TERMINAL, True, output=result[:5000])
        except asyncio.TimeoutError:
            return ToolResult(ToolName.RUN_TERMINAL, False, "", error=f"Command timed out after {timeout}s")
        except Exception as e:
            return ToolResult(ToolName.RUN_TERMINAL, False, "", error=str(e))

    async def run(self, user_input: str) -> str:
        resolved_system = await self._build_system_prompt(user_input)

        self.messages = [Message(role=Role.SYSTEM, content=resolved_system)]
        self.messages.append(Message(role=Role.USER, content=user_input))
        self.turn_count = 0

        while self.turn_count < self.config.max_turns:
            self.turn_count += 1

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
                    tc_id = tc.get("id", "")
                    result = await self._execute_tool(tc)
                    if not result.success and result.error:
                        print(f"  [tool error] {result.error}", file=sys.stderr)
                    self.messages.append(Message(
                        role=Role.TOOL,
                        content=result.output or result.error or "",
                        tool_call_id=tc_id,
                    ))
                continue

            if reply.content:
                self.messages.append(reply)
                await self._store_memory(user_input, reply.content)
                self.blocks.remember_exchange(user_input, reply.content)
                return reply.content

        return "Agent reached maximum turn limit."

    async def _build_system_prompt(self, user_input: str) -> str:
        system = self.config.system_prompt or SYSTEM_PROMPT

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
                    injection_block = f"\n\n[Injection: {inj.name}]\n{rendered}"

                    if inj.urls:
                        summaries = await self.summariser.summarise_urls(inj)
                        for s in summaries:
                            injection_block += f"\n[Web Summary: {s['url']}]\n{s['summary']}"
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

        return system

    def _parse_inline_tool_call(self, content: str) -> dict | None:
        import re
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

        func = data.get("function", {})
        name = data.get("name") or func.get("name", "")
        raw_args = (
            data.get("arguments")
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

    async def _execute_tool(self, tc: dict) -> ToolResult:
        name = tc.get("function", {}).get("name", "")
        args_raw = tc.get("function", {}).get("arguments", "{}")
        args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw

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
            "run_terminal": lambda: self.run_terminal(args.get("command", ""), args.get("workdir", ""), args.get("timeout", 30)),
        }

        handler = tool_map.get(name)
        if not handler:
            return ToolResult(ToolName.RUN_COMMAND, False, "", error=f"Unknown tool: {name}")

        result = handler()
        if asyncio.iscoroutine(result):
            result = await result
        return result

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
