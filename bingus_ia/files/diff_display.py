import difflib
import sys


def unified_diff(old_text: str, new_text: str, path: str, n: int = 3) -> str:
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        n=n,
    )
    return "".join(diff)


def print_diff(old_text: str, new_text: str, path: str) -> None:
    diff = unified_diff(old_text, new_text, path)
    if not diff:
        return
    out = sys.stdout
    for line in diff.splitlines(keepends=True):
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            out.write(f"\033[36m{line}\033[0m")
        elif line.startswith("+"):
            out.write(f"\033[32m{line}\033[0m")
        elif line.startswith("-"):
            out.write(f"\033[31m{line}\033[0m")
        else:
            out.write(line)
    out.flush()


def print_creation(content: str, path: str) -> None:
    out = sys.stdout
    out.write(f"\033[36m--- Created: {path}\033[0m\n")
    for line in content.splitlines(keepends=True):
        out.write(f"\033[32m+ {line}\033[0m")
    out.flush()
