from pathlib import Path

from bingus_ia.core.types import ToolResult, ToolName
from bingus_ia.files.diff_display import print_diff, print_creation


class FileEditor:
    def __init__(self, workspace_dir: str):
        self.workspace = Path(workspace_dir).resolve()

    def set_workspace(self, path: str) -> None:
        self.workspace = Path(path).resolve()

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = self.workspace / p
        p = p.resolve()
        if not str(p).startswith(str(self.workspace)):
            raise PermissionError(f"Path {p} is outside workspace")
        return p

    def _rel(self, target: Path) -> str:
        try:
            return str(target.relative_to(self.workspace))
        except ValueError:
            return str(target)

    def edit_file(self, path: str, old_string: str, new_string: str) -> ToolResult:
        try:
            target = self._resolve(path)

            if not old_string and not target.is_file():
                return self.write_file(path, new_string)

            if not target.is_file():
                return ToolResult(ToolName.EDIT_FILE, False, output="", error=f"File not found: {path}")

            content = target.read_text(encoding="utf-8")

            if not old_string:
                new_content = content + new_string
                target.write_text(new_content, encoding="utf-8")
                rp = self._rel(target)
                print_diff(content, new_content, rp)
                return ToolResult(
                    ToolName.EDIT_FILE, True,
                    output=f"Appended to {rp}: added {len(new_string)} chars",
                )

            if old_string not in content:
                return ToolResult(
                    ToolName.EDIT_FILE, False, output="",
                    error=f"old_string not found in {path}. Use search_code first to verify content.",
                )

            if content.count(old_string) > 1:
                return ToolResult(
                    ToolName.EDIT_FILE, False, output="",
                    error="Multiple matches for old_string. Provide more context.",
                )

            new_content = content.replace(old_string, new_string, 1)
            target.write_text(new_content, encoding="utf-8")

            rp = self._rel(target)
            print_diff(content, new_content, rp)

            return ToolResult(
                ToolName.EDIT_FILE, True,
                output=f"Edited {rp}: replaced {len(old_string)} chars with {len(new_string)} chars",
            )
        except Exception as e:
            return ToolResult(ToolName.EDIT_FILE, False, output="", error=str(e))

    def write_file(self, path: str, content: str) -> ToolResult:
        try:
            target = self._resolve(path)
            prev = target.read_text(encoding="utf-8") if target.exists() else ""
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

            rp = self._rel(target)
            if prev:
                print_diff(prev, content, rp)
            else:
                print_creation(content, rp)

            return ToolResult(
                ToolName.EDIT_FILE, True,
                output=f"Wrote {len(content)} chars to {rp}",
            )
        except Exception as e:
            return ToolResult(ToolName.EDIT_FILE, False, output="", error=str(e))
