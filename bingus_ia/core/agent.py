import asyncio
import json
import re
import sys

from bingus_ia.core.reducer import ContextReducer
from bingus_ia.core.types import (
    Message, Role, ToolName, ToolResult, AgentConfig,
)
from bingus_ia.core.working_memory import WorkingMemory
from bingus_ia.files.reader import FileReader
from bingus_ia.files.editor import FileEditor
from bingus_ia.llm.base import BaseLLMClient
from bingus_ia.llm.factory import create_llm_client

SYSTEM_PROMPT = """You are a code editor agent.  You can ONLY read and edit the file
currently open in the GUI editor.  Do not try to access any other files.

Each turn decide ONE action:
  - read_file  — read lines from the open file
  - edit_file  — replace text in the open file
  - write_file — overwrite the open file

Use function-calling.  If unsupported, output JSON:
  {"name": "tool_name", "arguments": {...}}

Rules:
  - A file preview is shown below under "Open file in editor".
  - After each tool result it is compressed into the [Working Memory] block above.
  - When you have enough information, stop calling tools and write your final answer."""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read lines from the currently open file",
            "parameters": {
                "type": "object",
                "properties": {
                    "offset": {"type": "integer", "description": "Line offset"},
                    "limit": {"type": "integer", "description": "Max lines"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace exact old_string with new_string in the currently open file",
            "parameters": {
                "type": "object",
                "properties": {
                    "old_string": {"type": "string", "description": "Exact text to replace"},
                    "new_string": {"type": "string", "description": "Replacement text"},
                },
                "required": ["old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Overwrite the currently open file with new content",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "File content"},
                },
                "required": ["content"],
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
        self.messages: list[Message] = []
        self.turn_count = 0
        self.wm = WorkingMemory()
        self.reducer = ContextReducer(llm=self.llm)
        self.current_file_path: str | None = None
        self.current_file_content: str = ""
        self.show_prompt = False
        self._compress_attempts = 0

    def set_current_file(self, path: str | None, content: str = ""):
        self.current_file_path = path
        self.current_file_content = content

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
                    facts = await self.reducer.reduce(
                        result.output or result.error or "",
                        query=user_input,
                    )
                    self.wm.add(source_key, facts)

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
                f"Preview:\n```\n{snippet}\n```"
            )

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
        if name == "edit_file":
            return f'old="{args.get("old_string", "")[:40]}"'
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

        def _require_open_file() -> ToolResult | None:
            if not self.current_file_path:
                return ToolResult(ToolName.READ_FILE, False, "", error="No file is open in the GUI editor. Open a file first.")
            return None

        tool_map = {
            "read_file": lambda: (
                r if (r := _require_open_file()) is not None
                else self.reader.read_file(self.current_file_path, args.get("offset", 0), args.get("limit"))
            ),
            "edit_file": lambda: (
                r if (r := _require_open_file()) is not None
                else self.editor.edit_file(self.current_file_path, args.get("old_string", ""), args.get("new_string", ""))
            ),
            "write_file": lambda: (
                r if (r := _require_open_file()) is not None
                else self.editor.write_file(self.current_file_path, args.get("content", ""))
            ),
        }

        handler = tool_map.get(name)
        if not handler:
            return ToolResult(ToolName.READ_FILE, False, "", error=f"Unknown tool: {name}")

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

    async def close(self):
        await self.llm.close()
