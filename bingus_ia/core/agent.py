import re

from bingus_ia.core.types import Message, Role, AgentConfig
from bingus_ia.files.editor import FileEditor
from bingus_ia.files.region import RegionLocator
from bingus_ia.llm.base import BaseLLMClient
from bingus_ia.llm.factory import create_llm_client


SYSTEM_PROMPT = """You are a code editing agent. You receive code context and a user request.

Your job is to output a unified diff patch that applies the requested change.

Rules:
- Output ONLY a unified diff (diff -u format).
- Each hunk starts with `@@ -start,count +start,count @@`.
- Lines starting with `-` are removed, `+` are added, ` ` are context.
- Do NOT include explanation, markdown fences, or anything else outside the diff.
- If the request is to add new code, include sufficient context lines around the insertion point.
- If multiple changes are needed, include multiple hunks."""


class Agent:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.llm: BaseLLMClient = create_llm_client(config)
        self.editor = FileEditor(config.workspace_dir)
        self.locator = RegionLocator()
        self.current_file_path: str | None = None
        self.current_file_content: str = ""
        self.show_prompt = False

    def set_current_file(self, path: str | None, content: str = ""):
        self.current_file_path = path
        self.current_file_content = content

    async def run(self, user_input: str) -> str:
        if not self.current_file_path or not self.current_file_content:
            return "No file is open in the GUI editor. Open a file first."

        system = self._build_system_prompt(user_input)
        if self.show_prompt:
            print(f"  [plan] system: {len(system)} chars", flush=True)

        messages = [
            Message(role=Role.SYSTEM, content=system),
            Message(role=Role.USER, content=user_input),
        ]

        print(f"  [llm] calling {self.config.model}...", flush=True)
        for attempt in range(3):
            reply = await self.llm.chat(messages=messages)
            content = reply.content or ""
            if self.show_prompt:
                print(f"  [llm] reply ({len(content)} chars)", flush=True)

            diff = self._extract_diff(content)
            if diff is None:
                if attempt < 2:
                    print(f"  [llm] no diff found, retrying ({attempt+1}/3)...", flush=True)
                    messages.append(reply)
                    messages.append(Message(
                        role=Role.USER,
                        content="Output ONLY a unified diff. No explanations, no markdown.",
                    ))
                    continue
                return "Model did not produce a valid diff after 3 attempts."

            result = self.editor.apply_patch(self.current_file_path, diff)
            if not result.success:
                return f"Failed to apply patch: {result.error}"

            return f"Applied patch: {result.output}"

        return "No valid diff produced."

    def _build_system_prompt(self, user_input: str) -> str:
        system = self.config.system_prompt or SYSTEM_PROMPT
        source = self.current_file_content
        region = self.locator.locate(source, user_input)
        context = self.locator.extract(source, region, user_input)

        system += (
            f"\n\nFile: {self.current_file_path}\n"
            f"Lines: {source.count(chr(10)) + 1}\n\n"
            f"{context}"
        )
        return system

    def _extract_diff(self, content: str) -> str | None:
        lines = content.splitlines()
        diff_lines = []
        in_diff = False
        for line in lines:
            if line.startswith("--- ") or line.startswith("+++ "):
                in_diff = True
            if in_diff:
                if line.startswith("```"):
                    break
                diff_lines.append(line)
        if diff_lines:
            return "\n".join(diff_lines)

        fence_match = re.search(
            r"```(?:diff)?\s*\n(.*?)\n```",
            content,
            re.DOTALL,
        )
        if fence_match:
            return fence_match.group(1).strip()

        return None

    async def close(self):
        await self.llm.close()
