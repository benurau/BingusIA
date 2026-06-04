from pathlib import Path

import yaml

from bingus_ia.core.types import ToolResult, ToolName

MEMORY_DIR = ".bingus_memory"
TOKEN_BUDGET = 300
CHARS_PER_TOKEN = 4
CHAR_BUDGET = TOKEN_BUDGET * CHARS_PER_TOKEN

DEFAULT_BLOCKS = {
    "persona": "How the agent should behave and respond.\n",
    "human": "Details about the user (preferences, habits, constraints).\n",
    "project": "Codebase-specific knowledge (commands, architecture, conventions).\n",
}


class MemoryBlocks:
    def __init__(self, workspace_dir: str):
        self._dir = Path(workspace_dir) / MEMORY_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._seed_defaults()

    def _seed_defaults(self) -> None:
        for name, content in DEFAULT_BLOCKS.items():
            path = self._dir / f"{name}.md"
            if not path.exists():
                self.set_block(name, content)

    def _path(self, name: str) -> Path:
        return self._dir / f"{name}.md"

    def list_blocks(self) -> ToolResult:
        blocks = []
        for f in sorted(self._dir.glob("*.md")):
            meta = self._read_meta(f)
            content = f.read_text(encoding="utf-8")
            size = len(content)
            blocks.append(f"  {meta.get('label', f.stem)} ({size} chars) — {meta.get('description', '')}")
        if not blocks:
            return ToolResult(ToolName.RUN_COMMAND, True, "No memory blocks.")
        return ToolResult(ToolName.RUN_COMMAND, True, "\n".join(blocks))

    def get_block(self, name: str) -> str:
        path = self._path(name)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def set_block(self, name: str, content: str) -> ToolResult:
        path = self._path(name)
        meta = {
            "label": name,
            "description": DEFAULT_BLOCKS.get(name, "User-defined memory block").strip(),
        }
        frontmatter = yaml.dump(meta, allow_unicode=True).strip()
        full = f"---\n{frontmatter}\n---\n{content}"
        path.write_text(full, encoding="utf-8")
        return ToolResult(ToolName.RUN_COMMAND, True, f"Memory block '{name}' updated ({len(content)} chars).")

    def replace_in_block(self, name: str, old: str, new: str) -> ToolResult:
        path = self._path(name)
        if not path.exists():
            return ToolResult(ToolName.RUN_COMMAND, False, "", error=f"Block '{name}' not found.")
        content = path.read_text(encoding="utf-8")
        if old not in content:
            return ToolResult(ToolName.RUN_COMMAND, False, "", error=f"Text not found in block '{name}'.")
        content = content.replace(old, new, 1)
        path.write_text(content, encoding="utf-8")
        return ToolResult(ToolName.RUN_COMMAND, True, f"Memory block '{name}' updated.")

    def _read_meta(self, path: Path) -> dict:
        text = path.read_text(encoding="utf-8")
        if text.startswith("---"):
            end = text.find("---", 3)
            if end != -1:
                try:
                    return yaml.safe_load(text[3:end]) or {}
                except yaml.YAMLError:
                    pass
        return {}

    def render_for_prompt(self) -> str:
        blocks = []
        for f in self._dir.glob("*.md"):
            content = f.read_text(encoding="utf-8").strip()
            content = self._strip_frontmatter(content)
            if not content:
                continue
            mtime = f.stat().st_mtime
            label = self._read_meta(f).get("label", f.stem)
            blocks.append((mtime, label, content))
        blocks.sort(key=lambda x: x[0], reverse=True)
        parts = []
        total = 0
        for _, label, content in blocks:
            line = f"[Memory: {label}]\n{content}"
            if total + len(line) > CHAR_BUDGET:
                break
            total += len(line)
            parts.append(line)
        return "\n\n".join(parts)

    def remember_exchange(self, prompt: str, response: str) -> None:
        exchange = f"You: {prompt}\nBingus: {response}"
        counter = self._next_exchange_counter()
        name = f"exchange-{counter:04d}"
        path = self._dir / f"{name}.md"
        meta = {
            "label": "exchange",
            "description": "Previous conversation exchange",
        }
        frontmatter = yaml.dump(meta, allow_unicode=True).strip()
        path.write_text(f"---\n{frontmatter}\n---\n{exchange}", encoding="utf-8")
        self._evict_old_blocks()

    def _next_exchange_counter(self) -> int:
        max_n = 0
        for f in self._dir.glob("exchange-*.md"):
            stem = f.stem
            parts = stem.split("-", 1)
            if len(parts) == 2 and parts[1].isdigit():
                max_n = max(max_n, int(parts[1]))
        return max_n + 1

    def _evict_old_blocks(self) -> None:
        blocks = []
        for f in self._dir.glob("*.md"):
            content = f.read_text(encoding="utf-8").strip()
            stripped = self._strip_frontmatter(content)
            mtime = f.stat().st_mtime
            label = self._read_meta(f).get("label", f.stem)
            line = f"[Memory: {label}]\n{stripped}"
            blocks.append((mtime, label, line, f))
        blocks.sort(key=lambda x: x[0], reverse=True)
        total = 0
        over_budget = []
        for mtime, label, line, f in blocks:
            if total + len(line) > CHAR_BUDGET:
                over_budget.append((label, f))
            else:
                total += len(line)
        for label, f in over_budget:
            if label in DEFAULT_BLOCKS:
                continue
            if f.exists():
                f.unlink()

    def _strip_frontmatter(self, text: str) -> str:
        if text.startswith("---"):
            end = text.find("---", 3)
            if end != -1:
                return text[end + 3:].strip()
        return text
