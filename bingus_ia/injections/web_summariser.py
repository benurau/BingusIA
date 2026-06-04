import re
from typing import Optional

import httpx

from bingus_ia.core.types import Injection
from bingus_ia.llm.base import BaseLLMClient

SUMMARISE_PROMPT = """Summarise the key technical information from this web page content in 3-5 sentences.
Focus on code practices, architecture decisions, APIs, or configuration details relevant to a programming assistant.

Content:
{content}

Summary:"""


class WebSummariser:
    def __init__(self, llm: BaseLLMClient):
        self.llm = llm
        self._http = httpx.Client(timeout=15.0, follow_redirects=True)

    async def summarise_urls(self, injection: Injection) -> list[dict[str, str]]:
        results = []
        for url in injection.urls:
            try:
                raw = self._fetch(url)
                if not raw:
                    results.append({"url": url, "summary": "[Could not fetch]"})
                    continue
                text = self._extract_text(raw)
                summary = await self._summarise(text)
                results.append({"url": url, "summary": summary})
            except Exception as e:
                results.append({"url": url, "summary": f"[Error: {e}]"})
        return results

    def _fetch(self, url: str) -> Optional[str]:
        resp = self._http.get(url)
        resp.raise_for_status()
        return resp.text

    def _extract_text(self, html: str) -> str:
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "\n".join(lines[:200])

    async def _summarise(self, text: str) -> str:
        prompt = SUMMARISE_PROMPT.format(content=text[:3000])
        from bingus_ia.core.types import Message, Role
        msg = Message(role=Role.USER, content=prompt)
        reply = await self.llm.chat([msg])
        return reply.content.strip()[:500]

    def close(self):
        self._http.close()
