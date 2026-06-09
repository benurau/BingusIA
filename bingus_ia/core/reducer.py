"""Context reducer — extract relevant sections, compress to bullet facts.

Two-stage pipeline:
  1. Heuristic section extraction (truncate or keyword-scored).
  2. LLM-based compression (async, fallback to heuristic).
"""


class ContextReducer:
    def __init__(self, llm=None):
        self._llm = llm

    async def reduce(self, text: str, query: str = "", max_bullets: int = 10) -> list[str]:
        if not text or not text.strip():
            return ["[No content]"]
        if self._llm and len(text) > 3000:
            return await self._llm_compress(text, query, max_bullets)
        return self._heuristic_compress(text, max_bullets)

    async def _llm_compress(self, text: str, query: str, max_bullets: int) -> list[str]:
        prompt = (
            f"Summarize the following as {max_bullets} concise bullet-point facts. "
            f"Keep each bullet under 200 characters. Preserve code, paths, "
            f"and URLs verbatim. Omit filler.\n\n{text[:4000]}"
        )
        try:
            from bingus_ia.core.types import Message, Role
            reply = await self._llm.chat([Message(role=Role.USER, content=prompt)])
            content = reply.content or ""
            bullets = [
                b.lstrip("- *").strip()
                for b in content.split("\n")
                if b.strip().startswith(("-", "*"))
            ]
            return [b for b in bullets if b][:max_bullets]
        except Exception:
            return self._heuristic_compress(text, max_bullets)

    def _heuristic_compress(self, text: str, max_bullets: int) -> list[str]:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        bullets = []
        for line in lines:
            if len(line) > 30:
                bullets.append(line[:250])
                if len(bullets) >= max_bullets:
                    break
        return bullets or ["[Content available]"]
