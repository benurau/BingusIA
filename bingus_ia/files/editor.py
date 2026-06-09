import os
import re
from pathlib import Path

from bingus_ia.core.types import ToolResult, ToolName
from bingus_ia.files.diff_display import print_diff, print_creation


class FileEditor:
    def __init__(self, workspace_dir: str):
        self.workspace = Path(workspace_dir).resolve()

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = self.workspace / p
        try:
            p = p.resolve()
        except PermissionError:
            raise PermissionError(f"Cannot access '{path}' — permission denied. Check folder permissions or close programs using it.")
        except OSError as e:
            raise PermissionError(f"Cannot access '{path}': {e}")
        if not str(p).startswith(str(self.workspace)):
            raise PermissionError(f"Path '{p}' is outside the workspace '{self.workspace}'")
        return p

    def _rel(self, target: Path) -> str:
        try:
            return str(target.relative_to(self.workspace))
        except ValueError:
            return str(target)

    def _check_writable(self, target: Path) -> str | None:
        if target.exists():
            if not os.access(target, os.W_OK):
                return (f"Cannot write to '{self._rel(target)}' — permission denied. "
                        "The file may be read-only or locked by another program.")
            return None
        parent = target.parent
        if not parent.exists():
            return None
        if not os.access(parent, os.W_OK):
            return (f"Cannot create files in '{self._rel(parent)}' — permission denied. "
                    "Check folder permissions or close programs using it.")
        return None

    def edit_file(self, path: str, old_string: str, new_string: str) -> ToolResult:
        try:
            target = self._resolve(path)

            if not old_string and not target.is_file():
                return self.write_file(path, new_string)

            if not target.is_file():
                return ToolResult(ToolName.EDIT_FILE, False, output="", error=f"File not found: {path}")

            write_err = self._check_writable(target)
            if write_err:
                return ToolResult(ToolName.EDIT_FILE, False, output="", error=write_err)


            try:
                content = target.read_text(encoding="utf-8")
            except PermissionError:
                return ToolResult(ToolName.EDIT_FILE, False, output="",
                                  error=f"Cannot read '{self._rel(target)}' — permission denied. Check file/folder permissions.")
            except Exception as e:
                return ToolResult(ToolName.EDIT_FILE, False, output="",
                                  error=f"Cannot read '{self._rel(target)}': {e}")

            if not old_string:
                new_content = content + new_string
                try:
                    target.write_text(new_content, encoding="utf-8")
                except PermissionError:
                    return ToolResult(ToolName.EDIT_FILE, False, output="",
                                      error=f"Cannot write to '{self._rel(target)}' — permission denied. Check if the file is read-only or locked.")
                except OSError as e:
                    return ToolResult(ToolName.EDIT_FILE, False, output="",
                                      error=f"Cannot write to '{self._rel(target)}': {e}")
                rp = self._rel(target)
                print_diff(content, new_content, rp)
                return ToolResult(
                    ToolName.EDIT_FILE, True,
                    output=f"Appended to {rp}: added {len(new_string)} chars",
                )

            if old_string not in content:
                return ToolResult(
                    ToolName.EDIT_FILE, False, output="",
                    error=f"old_string not found in {path}. Use read_file first to verify content.",
                )

            if content.count(old_string) > 1:
                return ToolResult(
                    ToolName.EDIT_FILE, False, output="",
                    error="Multiple matches for old_string. Provide more context.",
                )

            new_content = content.replace(old_string, new_string, 1)
            try:
                target.write_text(new_content, encoding="utf-8")
            except PermissionError:
                return ToolResult(ToolName.EDIT_FILE, False, output="",
                                  error=f"Cannot write to '{self._rel(target)}' — permission denied.")
            except OSError as e:
                return ToolResult(ToolName.EDIT_FILE, False, output="",
                                  error=f"Cannot write to '{self._rel(target)}': {e}")

            rp = self._rel(target)
            print_diff(content, new_content, rp)

            return ToolResult(
                ToolName.EDIT_FILE, True,
                output=f"Edited {rp}: replaced {len(old_string)} chars with {len(new_string)} chars",
            )
        except PermissionError as e:
            return ToolResult(ToolName.EDIT_FILE, False, output="", error=str(e))
        except Exception as e:
            return ToolResult(ToolName.EDIT_FILE, False, output="", error=f"Error editing '{path}': {e}")

    def apply_patch(self, path: str, diff_text: str) -> ToolResult:
        target = self._resolve(path)
        if not target.is_file():
            return ToolResult(ToolName.EDIT_FILE, False, output="", error=f"File not found: {path}")

        try:
            old = target.read_text(encoding="utf-8")
        except PermissionError:
            return ToolResult(ToolName.EDIT_FILE, False, output="",
                              error=f"Cannot read '{self._rel(target)}' — permission denied.")

        new_text = self._apply_unified_diff(old, diff_text)
        if new_text is None:
            return ToolResult(ToolName.EDIT_FILE, False, output="",
                              error="Failed to apply unified diff. Check diff format.")

        write_err = self._check_writable(target)
        if write_err:
            return ToolResult(ToolName.EDIT_FILE, False, output="", error=write_err)

        try:
            target.write_text(new_text, encoding="utf-8")
        except PermissionError:
            return ToolResult(ToolName.EDIT_FILE, False, output="",
                              error=f"Cannot write to '{self._rel(target)}' — permission denied.")
        except OSError as e:
            return ToolResult(ToolName.EDIT_FILE, False, output="",
                              error=f"Cannot write to '{self._rel(target)}': {e}")

        rp = self._rel(target)
        print_diff(old, new_text, rp)
        return ToolResult(
            ToolName.EDIT_FILE, True,
            output=f"Applied patch to {rp} ({len(new_text)} chars)",
        )

    def _apply_unified_diff(self, old_text: str, diff_text: str) -> str | None:
        import difflib
        old_lines = old_text.splitlines(keepends=True)
        hunks = self._parse_diff(diff_text)
        if hunks is None:
            return None
        result = list(old_lines)
        for start, end, new_lines in sorted(hunks, key=lambda x: -x[0]):
            result[start:end] = [l + "\n" if not l.endswith("\n") else l for l in new_lines]
        return "".join(result)

    def _parse_diff(self, diff_text: str) -> list[tuple[int, int, list[str]]] | None:
        hunks: list[tuple[int, int, list[str]]] = []
        for block in re.split(r"(?=^@@ )", diff_text.strip(), flags=re.MULTILINE):
            block = block.strip()
            if not block or block.startswith("---") or block.startswith("+++"):
                continue
            m = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", block)
            if not m:
                continue
            old_start = int(m.group(1))
            old_count = int(m.group(2)) if m.group(2) else 1
            old_end = old_start + old_count - 1
            body_start = m.end()
            new_lines: list[str] = []
            for line in block[body_start:].splitlines():
                if line.startswith("+") and not line.startswith("+++"):
                    new_lines.append(line[1:])
                elif line.startswith(" ") or line.startswith("\n"):
                    new_lines.append(line[1:] if line.startswith(" ") else line)
            hunks.append((old_start - 1, old_end, new_lines))
        return hunks if hunks else None

    def write_file(self, path: str, content: str) -> ToolResult:
        try:
            target = self._resolve(path)
            write_err = self._check_writable(target)
            if write_err:
                return ToolResult(ToolName.EDIT_FILE, False, output="", error=write_err)

            prev = ""
            try:
                prev = target.read_text(encoding="utf-8") if target.exists() else ""
            except PermissionError:
                pass

            try:
                target.parent.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                return ToolResult(ToolName.EDIT_FILE, False, output="",
                                  error=f"Cannot create directory '{self._rel(target.parent)}' — permission denied.")
            except Exception as e:
                return ToolResult(ToolName.EDIT_FILE, False, output="",
                                  error=f"Cannot create directory '{self._rel(target.parent)}': {e}")

            try:
                target.write_text(content, encoding="utf-8")
            except PermissionError:
                return ToolResult(ToolName.EDIT_FILE, False, output="",
                                  error=f"Cannot write to '{self._rel(target)}' — permission denied. Check if the file is read-only or the folder is restricted.")
            except OSError as e:
                return ToolResult(ToolName.EDIT_FILE, False, output="",
                                  error=f"Cannot write to '{self._rel(target)}': {e}")

            rp = self._rel(target)
            if prev:
                print_diff(prev, content, rp)
            else:
                print_creation(content, rp)

            return ToolResult(
                ToolName.EDIT_FILE, True,
                output=f"Wrote {len(content)} chars to {rp}",
            )
        except PermissionError as e:
            return ToolResult(ToolName.EDIT_FILE, False, output="", error=str(e))
        except Exception as e:
            return ToolResult(ToolName.EDIT_FILE, False, output="", error=f"Error writing '{path}': {e}")
