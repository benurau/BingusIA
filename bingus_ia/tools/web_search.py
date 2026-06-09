import re

import httpx
import trafilatura
from ddgs import DDGS

from bingus_ia.core.types import ToolResult, ToolName


_CHUNK_SIZE = 4000  # ~1000 tokens


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
            downloaded = trafilatura.fetch_url(url)
            if downloaded is None:
                return ToolResult(ToolName.WEB_FETCH, True, f"URL: {url}\n\n[Could not fetch page]")
            extracted = trafilatura.extract(downloaded, output_format="markdown",
                                            with_metadata=False, include_links=True)
            if not extracted or not extracted.strip():
                return ToolResult(ToolName.WEB_FETCH, True, f"URL: {url}\n\n[No extractable content found]")
            chunks = self._chunk_text(extracted)
            output = self._format_chunks(url, chunks)
            return ToolResult(ToolName.WEB_FETCH, True, output[:8000])
        except Exception as e:
            return ToolResult(ToolName.WEB_FETCH, False, "", error=str(e))

    def fetch_html(self, url: str) -> ToolResult:
        try:
            downloaded = trafilatura.fetch_url(url)
            if downloaded is None:
                return ToolResult(ToolName.WEB_FETCH, True, f"URL: {url}\n\n[Could not fetch page]")
            extracted = trafilatura.extract(downloaded, output_format="xml",
                                            with_metadata=False, include_links=True,
                                            include_images=False, include_tables=True,
                                            include_formatting=True)
            if not extracted or not extracted.strip():
                return ToolResult(ToolName.WEB_FETCH, True, f"URL: {url}\n\n[No extractable content found]")
            body = self._strip_metadata(extracted)
            chunks = self._chunk_text(body)
            output = self._format_chunks(url, chunks)
            return ToolResult(ToolName.WEB_FETCH, True, output[:8000])
        except Exception as e:
            return ToolResult(ToolName.WEB_FETCH, False, "", error=str(e))

    def _chunk_text(self, text: str) -> list[str]:
        paragraphs = re.split(r"\n\s*\n", text.strip())
        chunks: list[str] = []
        current = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(current) + len(para) + 1 > _CHUNK_SIZE and current:
                chunks.append(current.strip())
                current = para
            else:
                current = (current + "\n\n" + para) if current else para
        if current:
            chunks.append(current.strip())
        return chunks if chunks else [text.strip()]

    def _format_chunks(self, url: str, chunks: list[str]) -> str:
        header = f"URL: {url}\n\n"
        if not chunks:
            return header + "[No content extracted]"
        parts = [header + f"[Content — {len(chunks)} chunk(s)]"]
        for i, chunk in enumerate(chunks[:5], 1):
            parts.append(f"\n--- Chunk {i}/{len(chunks)} ---\n{chunk}")
        if len(chunks) > 5:
            parts.append(f"\n... and {len(chunks) - 5} more chunk(s).")
        return "\n".join(parts)

    @staticmethod
    def _strip_metadata(text: str) -> str:
        lines = text.split("\n")
        content_start = 0
        for i, line in enumerate(lines):
            if line.strip() == "":
                content_start = i
                break
        return "\n".join(lines[content_start:]).strip()

    def close(self):
        self._http.close()
