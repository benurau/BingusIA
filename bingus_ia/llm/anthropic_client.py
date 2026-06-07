import json
import httpx
from typing import AsyncGenerator

from bingus_ia.core.types import Message, Role
from bingus_ia.llm.base import BaseLLMClient, LLMError


class AnthropicClient(BaseLLMClient):
    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-sonnet-4-20250514",
        base_url: str = "https://api.anthropic.com/v1",
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=120.0)
        self._headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    def _convert_messages(self, messages: list[Message]) -> tuple[list[dict], str]:
        system = ""
        converted = []
        i = 0
        while i < len(messages):
            m = messages[i]
            if m.role == Role.SYSTEM:
                system = m.content
                i += 1
            elif m.role == Role.USER:
                converted.append({"role": "user", "content": m.content})
                i += 1
            elif m.role == Role.ASSISTANT:
                blocks = []
                if m.content:
                    blocks.append({"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    args = tc["function"]["arguments"]
                    if isinstance(args, str):
                        args = json.loads(args)
                    blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", f"toolu_{i}_{len(blocks)}"),
                        "name": tc["function"]["name"],
                        "input": args,
                    })
                converted.append({"role": "assistant", "content": blocks})
                i += 1
            elif m.role == Role.TOOL:
                tool_results = []
                while i < len(messages) and messages[i].role == Role.TOOL:
                    tm = messages[i]
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tm.tool_call_id,
                        "content": tm.content,
                    })
                    i += 1
                converted.append({"role": "user", "content": tool_results})

        return converted, system

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        stream: bool = False,
    ) -> Message | AsyncGenerator[str, None]:
        converted, system = self._convert_messages(messages)

        payload: dict = {
            "model": self.model,
            "messages": converted,
            "max_tokens": 8192,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = [
                {
                    "name": t["function"]["name"],
                    "description": t["function"].get("description", ""),
                    "input_schema": t["function"]["parameters"],
                }
                for t in tools
            ]

        resp = await self._client.post(
            f"{self.base_url}/messages",
            json=payload,
            headers=self._headers,
        )
        if resp.status_code != 200:
            raise LLMError(f"Anthropic returned {resp.status_code}: {resp.text}")

        if stream:
            return self._stream(resp)

        body = resp.json()
        return self._parse_reply(body)

    def _parse_reply(self, body: dict) -> Message:
        content = body.get("content", [])
        text = ""
        tool_calls = []

        for block in content:
            if block["type"] == "text":
                text += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append({
                    "id": block["id"],
                    "function": {
                        "name": block["name"],
                        "arguments": block["input"],
                    },
                })

        return Message(
            role=Role.ASSISTANT,
            content=text,
            tool_calls=tool_calls,
        )

    async def _stream(self, resp: httpx.Response) -> AsyncGenerator[str, None]:
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                line = line[6:]
            if not line or line == "[DONE]":
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            if chunk.get("type") == "content_block_delta":
                delta = chunk.get("delta", {})
                if delta.get("type") == "text_delta":
                    if content := delta.get("text", ""):
                        yield content

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        raise LLMError(
            "Anthropic does not support embeddings. "
            "Use a different provider for embeddings, or set memory_enabled=false."
        )

    async def list_models(self) -> list[dict]:
        resp = await self._client.get(
            f"{self.base_url}/models",
            headers=self._headers,
        )
        if resp.status_code != 200:
            raise LLMError(f"Failed to list models: {resp.status_code}")
        return resp.json().get("data", [])

    async def close(self):
        await self._client.aclose()
