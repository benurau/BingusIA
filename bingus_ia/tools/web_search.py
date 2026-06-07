import re

import httpx
from ddgs import DDGS

from bingus_ia.core.types import ToolResult, ToolName


class WebSearch:
    def __init__(self):
        self._http = httpx.Client(timeout=15.0, follow_redirects=True)

    def search(self, query: str, num_results: int = 5) -> ToolResult:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=num_results))
        except Exception as e:
            return ToolResult(ToolName.WEB_SEARCH, False, "", error=str(e))
        if not results:
            return ToolResult(ToolName.WEB_SEARCH, True, "No results found.")
        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            url = r.get("href", "")
            snippet = r.get("body", "")
            lines.append(f"{i}. {title}")
            lines.append(f"   {url}")
            lines.append(f"   {snippet}")
            lines.append("")
        return ToolResult(ToolName.WEB_SEARCH, True, "\n".join(lines).strip())

    def fetch(self, url: str) -> ToolResult:
        try:
            resp = self._http.get(url)
            resp.raise_for_status()
            text = self._extract_text(resp.text)
            if not text.strip():
                return ToolResult(ToolName.WEB_FETCH, True, f"URL: {url}\n\n[No extractable content found]")
            return ToolResult(ToolName.WEB_FETCH, True, f"URL: {url}\n\n{text[:5000]}")
        except Exception as e:
            return ToolResult(ToolName.WEB_FETCH, False, "", error=str(e))

    def fetch_html(self, url: str) -> ToolResult:
        try:
            resp = self._http.get(url)
            resp.raise_for_status()
            text = re.sub(r"<script[^>]*>.*?</script>", "", resp.text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
            if not text.strip():
                return ToolResult(ToolName.WEB_FETCH, True, f"URL: {url}\n\n[No HTML content found]")
            return ToolResult(ToolName.WEB_FETCH, True, f"URL: {url}\n\n{text[:8000]}")
        except Exception as e:
            return ToolResult(ToolName.WEB_FETCH, False, "", error=str(e))

    def _extract_text(self, html: str) -> str:
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "\n".join(lines[:200])

    def close(self):
        self._http.close()
