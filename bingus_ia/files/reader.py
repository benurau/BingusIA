from pathlib import Path

from bingus_ia.core.types import ToolResult, ToolName


class FileReader:
    def __init__(self, workspace_dir: str):
        self.workspace = Path(workspace_dir).resolve()

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = self.workspace / p
        try:
            p = p.resolve()
        except PermissionError:
            raise PermissionError(f"Cannot access '{path}' — permission denied. The path may be read-only, on a restricted drive, or locked by another process.")
        except OSError as e:
            raise PermissionError(f"Cannot access '{path}': {e}")
        if not str(p).startswith(str(self.workspace)):
            raise PermissionError(f"Path '{p}' is outside the workspace '{self.workspace}'")
        return p

    def read_file(self, path: str, offset: int = 0, limit: int = 2000) -> ToolResult:
        try:
            target = self._resolve(path)
            if not target.is_file():
                return ToolResult(ToolName.READ_FILE, False, output="", error=f"File not found: {path}")
            try:
                lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
            except PermissionError:
                return ToolResult(ToolName.READ_FILE, False, output="",
                                  error=f"Cannot read '{path}' — permission denied. Check file/folder permissions or close programs using it.")
            total = len(lines)
            start = max(0, offset)
            end = min(total, start + limit) if limit else total
            snippet = "".join(lines[start:end])
            info = f"--- {path} (lines {start+1}-{end} of {total}) ---\n"
            return ToolResult(ToolName.READ_FILE, True, output=info + snippet)
        except PermissionError as e:
            return ToolResult(ToolName.READ_FILE, False, output="", error=str(e))
        except Exception as e:
            return ToolResult(ToolName.READ_FILE, False, output="", error=f"Error reading '{path}': {e}")


