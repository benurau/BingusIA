import ast
import re
from dataclasses import dataclass, field



@dataclass
class CodeRegion:
    start_line: int
    end_line: int
    target_name: str
    target_type: str
    context_start: int
    context_end: int
    deps: list[str] = field(default_factory=list)


SURROUNDING_LINES = 50
MAX_CONTEXT_LINES = 80


class RegionLocator:
    def locate(self, source: str, query: str) -> CodeRegion | None:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return self._locate_fallback(source, query)

        candidates: list[tuple[int, ast.AST, str]] = []
        query_lower = query.lower()

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name
                rank = self._rank(name, query_lower, node)
                candidates.append((rank, node, "function"))
            elif isinstance(node, ast.ClassDef):
                name = node.name
                rank = self._rank(name, query_lower, node)
                candidates.append((rank, node, "class"))

        if not candidates:
            return self._whole_file(len(source.splitlines()))

        candidates.sort(key=lambda x: -x[0])
        best = candidates[0]
        rank, node, node_type = best

        if rank <= 1:
            is_add = any(w in query_lower for w in ["add ", "create ", "new ", "implement ", "write "])
            if is_add:
                return self._end_of_file(source, tree)

        target_start = node.lineno
        target_name = node.name if hasattr(node, "name") else name
        if hasattr(node, "end_lineno") and node.end_lineno:
            target_end = node.end_lineno
        else:
            target_end = self._guess_end(source, target_start)

        deps = self._one_hop_deps(tree, node)
        context_start = max(1, target_start - SURROUNDING_LINES)
        header_lines = 0
        for i in range(context_start - 1, min(context_start + 10, target_start)):
            line = source.splitlines()[i] if i < len(source.splitlines()) else ""
            if line.strip().startswith(("import ", "from ")):
                header_lines += 1
            else:
                break
        context_start = max(1, context_start - header_lines)
        context_end = min(len(source.splitlines()), target_end + SURROUNDING_LINES)

        if context_end - context_start + 1 > MAX_CONTEXT_LINES:
            mid = (target_start + target_end) // 2
            half = MAX_CONTEXT_LINES // 2
            context_start = max(1, mid - half)
            context_end = min(len(source.splitlines()), mid + half)

        return CodeRegion(
            start_line=target_start,
            end_line=target_end,
            target_name=target_name,
            target_type=node_type,
            context_start=context_start,
            context_end=context_end,
            deps=deps,
        )

    def extract(self, source: str, region: CodeRegion | None, query: str) -> str:
        lines = source.splitlines()
        parts = []

        if region:
            context_lines = lines[region.context_start - 1 : region.context_end]
            parts.append(f"# File context (lines {region.context_start}-{region.context_end})")
            if region.deps:
                parts.append(f"# Related symbols: {', '.join(region.deps[:8])}")
            parts.append("```")
            parts.extend(context_lines)
            parts.append("```")
            parts.append(
                f"\n# Target: {region.target_type} `{region.target_name}` "
                f"(lines {region.start_line}-{region.end_line})"
            )
        else:
            parts.append("# Full file (AST parse failed)")
            parts.append("```")
            parts.extend(lines[:200])
            if len(lines) > 200:
                parts.append("... (truncated)")
            parts.append("```")

        parts.append(f"\n# Request: {query}")
        return "\n".join(parts)

    def _rank(self, name: str, query_lower: str, node: ast.AST) -> int:
        score = 0
        name_lower = name.lower()

        keywords = [kw for kw in re.findall(r"[a-zA-Z_]\w*", query_lower) if len(kw) >= 3]
        for kw in keywords:
            if kw == name_lower:
                score += 10
            elif kw in name_lower or name_lower in kw:
                score += 5

        query_words = set(query_lower.split())
        name_words = set(re.split(r"[_ ]", name_lower))
        overlap = query_words & name_words
        score += len(overlap) * 3

        docstring = ast.get_docstring(node) or ""
        doc_lower = docstring.lower()
        for kw in [_f for _f in re.findall(r"[a-zA-Z_]\w*", query_lower) if len(_f) >= 3]:
            if kw in doc_lower:
                score += 2

        if not keywords:
            return 1

        return score

    def _guess_end(self, source: str, start: int) -> int:
        lines = source.splitlines()
        indent = None
        for i in range(start - 1, len(lines)):
            line = lines[i]
            if indent is None and line.strip():
                indent = len(line) - len(line.lstrip())
                continue
            if indent is not None:
                stripped = line.strip()
                if stripped and len(line) - len(stripped) <= indent and not stripped.startswith(("#", '"""', "'''")):
                    return i
        return len(lines)

    def _one_hop_deps(self, tree: ast.AST, target: ast.AST) -> list[str]:
        names = set()
        for node in ast.walk(target):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    names.add(node.func.id)

        imports = set()
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])

        used_imports = [imp for imp in sorted(imports) if imp in names]
        return used_imports[:8]

    def _end_of_file(self, source: str, tree: ast.AST) -> CodeRegion:
        lines = source.splitlines()
        last = len(lines)
        imports_end = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(("import ", "from ")):
                imports_end = i + 1
        context_start = max(1, imports_end)
        context_end = last
        indent_guide = ""
        for i in range(last - 1, -1, -1):
            stripped = lines[i].strip()
            if stripped and not stripped.startswith(("#", '"""', "'''")):
                indent_guide = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
                break
        return CodeRegion(
            start_line=last + 1,
            end_line=last + 1,
            target_name="(end of file)",
            target_type="insertion point",
            context_start=context_start,
            context_end=last,
            deps=[],
        )

    def _locate_fallback(self, source: str, query: str) -> CodeRegion | None:
        lines = source.splitlines()
        if not lines:
            return None
        line_count = len(lines)

        keywords = [kw for kw in re.findall(r"[a-zA-Z_]\w*", query) if len(kw) >= 3]

        scored: list[tuple[int, int]] = []
        for i, line in enumerate(lines):
            score = 0
            found: set[str] = set()
            for kw in keywords:
                if kw.lower() in line.lower():
                    found.add(kw.lower())
                    score += len(kw)
            dedup = len(found) * 10
            total = score + dedup
            if total > 0:
                scored.append((total, i))

        if not scored:
            return self._whole_file(line_count)

        scored.sort(key=lambda x: -x[0])
        best_line = scored[0][1]

        target_start = best_line + 1
        target_end = min(line_count, best_line + 11)

        context_start = max(1, best_line + 1 - 30)
        context_end = min(line_count, best_line + 1 + 50)

        return CodeRegion(
            start_line=target_start,
            end_line=target_end,
            target_name=lines[best_line].strip()[:40],
            target_type="(keyword match)",
            context_start=context_start,
            context_end=context_end,
            deps=[],
        )

    def _whole_file(self, line_count: int) -> CodeRegion:
        return CodeRegion(
            start_line=1,
            end_line=line_count,
            target_name="(file)",
            target_type="module",
            context_start=1,
            context_end=line_count,
        )
