import json
import httpx
from typing import AsyncGenerator

from bingus_ia.core.types import Message, Role
from bingus_ia.llm.base import BaseLLMClient, LLMError


class OllamaClient(BaseLLMClient):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "codellama:7b"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.AsyncClient(timeout=120.0)

    def _convert_messages(self, messages: list[Message]) -> list[dict]:
        result = []
        for m in messages:
            d = {"role": m.role.value, "content": m.content}
            if m.role == Role.TOOL and m.tool_call_id:
                d["tool_call_id"] = m.tool_call_id
            if m.role == Role.ASSISTANT and m.tool_calls:
                d["tool_calls"] = [
                    {
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"]
                            if isinstance(tc["function"]["arguments"], dict)
                            else json.loads(tc["function"]["arguments"]),
                        }
                    }
                    for tc in m.tool_calls
                ]
            result.append(d)
        return result

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        stream: bool = False,
    ) -> Message | AsyncGenerator[str, None]:
        payload = {
            "model": self.model,
            "messages": self._convert_messages(messages),
            "stream": stream,
        }

        if tools:
            payload["tools"] = tools

        resp = await self._client.post(f"{self.base_url}/api/chat", json=payload)

        if resp.status_code != 200:
            raise LLMError(f"Ollama returned {resp.status_code}: {resp.text}")

        if stream:
            return self._stream(resp.text)
        body = resp.json()
        reply = body["message"]
        return Message(
            role=Role(reply.get("role", "assistant")),
            content=reply.get("content") or "",
            tool_calls=reply.get("tool_calls") or [],
        )

    async def _stream(self, raw: str):
        for line in raw.strip().split("\n"):
            if not line:
                continue
            chunk = json.loads(line)
            if content := chunk.get("message", {}).get("content", ""):
                yield content

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        payload = {
            "model": model or self.model,
            "input": text,
        }
        resp = await self._client.post(f"{self.base_url}/api/embed", json=payload)
        if resp.status_code != 200:
            raise LLMError(f"Embedding failed: {resp.status_code}: {resp.text}")
        return resp.json()["embeddings"][0]

    async def list_models(self) -> list[dict]:
        resp = await self._client.get(f"{self.base_url}/api/tags")
        if resp.status_code != 200:
            raise LLMError(f"Failed to list models: {resp.status_code}")
        return resp.json().get("models", [])

    async def close(self):
        await self._client.aclose()
