import time
from typing import Optional

from bingus_ia.core.types import MemoryEntry, ToolResult, ToolName
from bingus_ia.llm.base import BaseLLMClient
from bingus_ia.memory.sqlite_store import SQLiteStore


class MemoryManager:
    def __init__(self, llm: BaseLLMClient, embedding_model: str = "nomic-embed-text"):
        self.llm = llm
        self.embedding_model = embedding_model
        self.store = SQLiteStore()

    async def remember(self, prompt: str, response: str, metadata: dict | None = None) -> str:
        try:
            embedding = await self.llm.embed(prompt, model=self.embedding_model)
        except Exception:
            embedding = []
        entry = MemoryEntry(
            id="",
            prompt=prompt,
            response=response,
            timestamp=time.time(),
            embedding=embedding,
            metadata=metadata or {},
        )
        return self.store.store(entry)

    async def recall(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        exact = self.store.search_by_text(query, limit=limit)
        semantic = await self._semantic_search(query, limit=limit)
        seen = set()
        merged = []
        for e in exact + semantic:
            if e.id not in seen:
                seen.add(e.id)
                merged.append(e)
        return merged[:limit]

    async def _semantic_search(self, query: str, limit: int) -> list[MemoryEntry]:
        try:
            query_embed = await self.llm.embed(query, model=self.embedding_model)
        except Exception:
            return []

        recent = self.store.get_recent(limit=100)
        if not recent:
            return []

        import struct
        scored = []
        for entry in recent:
            with self.store.store.db_path:
                import sqlite3
                with sqlite3.connect(self.store.db_path) as conn:
                    row = conn.execute(
                        "SELECT vector FROM embeddings WHERE memory_id = ?", (entry.id,)
                    ).fetchone()
            if not row:
                continue
            vec = list(struct.unpack(f"{len(row[0]) // 8}d", row[0]))
            score = self._cosine_similarity(query_embed, vec)
            scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:limit]]

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        return dot / (na * nb) if na and nb else 0.0

    def lookup(self, query: str, limit: int = 5) -> ToolResult:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        results = loop.run_until_complete(self.recall(query, limit))
        if not results:
            return ToolResult(ToolName.MEMORY_LOOKUP, True, output="No relevant memories found.")
        lines = []
        for r in results:
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(r.timestamp))
            lines.append(f"[{ts}] Q: {r.prompt[:100]}")
            lines.append(f"       A: {r.response[:200]}")
            lines.append("")
        return ToolResult(ToolName.MEMORY_LOOKUP, True, output="\n".join(lines))

    def get_recent(self, limit: int = 10) -> ToolResult:
        entries = self.store.get_recent(limit)
        if not entries:
            return ToolResult(ToolName.MEMORY_LOOKUP, True, output="No past sessions found.")
        lines = []
        for r in entries:
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(r.timestamp))
            lines.append(f"[{ts}] {r.prompt[:120]}")
        return ToolResult(ToolName.MEMORY_LOOKUP, True, output="\n".join(lines))
