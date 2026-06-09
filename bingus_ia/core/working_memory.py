"""Working memory — compressed per-source context store.

Each tool result is reduced to bullet-point facts and stored
per source.  Oldest entries are evicted when capacity is exceeded.
Total rendered output is capped to protect the context window.
"""


_RENDER_LIMIT = 6000  # characters (~1500 tokens) for the entire WM block


class WorkingMemory:
    def __init__(self, max_bytes_per_source: int = 2048, max_sources: int = 4):
        self._sources: dict[str, dict] = {}
        self._max_bytes = max_bytes_per_source
        self._max_sources = max_sources
        self._order: list[str] = []

    def add(self, key: str, facts: list[str], url: str = "") -> None:
        if key not in self._sources:
            if len(self._sources) >= self._max_sources:
                oldest = self._order.pop(0)
                del self._sources[oldest]
            self._sources[key] = {"url": url, "facts": [], "size": 0}
            self._order.append(key)
        entry = self._sources[key]
        for f in facts:
            if entry["size"] + len(f) > self._max_bytes:
                continue
            entry["facts"].append(f)
            entry["size"] += len(f)

    def render(self) -> str:
        if not self._sources:
            return ""
        parts = ["[Working Memory]"]
        for key in self._order:
            entry = self._sources[key]
            label = f"\n{key}: {entry['url']}" if entry["url"] else f"\n{key}"
            parts.append(label)
            for f in entry["facts"]:
                parts.append(f"  - {f}")
        rendered = "\n".join(parts)
        if len(rendered) > _RENDER_LIMIT:
            rendered = rendered[:_RENDER_LIMIT] + "\n... (truncated)"
        return rendered

    def clear(self) -> None:
        self._sources.clear()
        self._order.clear()

    @property
    def is_full(self) -> bool:
        return len(self._sources) >= self._max_sources
