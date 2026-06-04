import json
import httpx
from typing import AsyncGenerator

from bingus_ia.core.types import Message, Role
from bingus_ia.llm.base import BaseLLMClient, LLMError


class OpenAIClient(BaseLLMClient):
    def __init__(
        self,
        api_key: str = "",
        model: str = "gpt-4o",
        base_url: str = "https://api.openai.com/v1",
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=120.0)
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _convert_messages(self, messages: list[Message]) -> list[dict]:
        result = []
        for m in messages:
            if m.role == Role.TOOL:
                result.append({
                    "role": "tool",
                    "content": m.content,
                    "tool_call_id": m.tool_call_id,
                })
            elif m.role == Role.ASSISTANT:
                d = {"role": "assistant", "content": m.content}
                if m.tool_calls:
                    d["tool_calls"] = [
                        {
                            "id": tc.get("id", f"call_{i}"),
                            "type": "function",
                            "function": {
                                "name": tc["function"]["name"],
                                "arguments": json.dumps(tc["function"]["arguments"])
                                if isinstance(tc["function"]["arguments"], dict)
                                else tc["function"]["arguments"],
                            },
                        }
                        for i, tc in enumerate(m.tool_calls)
                    ]
                result.append(d)
            else:
                result.append({"role": m.role.value, "content": m.content})
        return result

    def _parse_reply(self, choice: dict) -> Message:
        msg = choice["message"]
        tool_calls = []
        for tc in msg.get("tool_calls", []):
            args = tc["function"]["arguments"]
            tool_calls.append({
                "id": tc["id"],
                "function": {
                    "name": tc["function"]["name"],
                    "arguments": json.loads(args) if isinstance(args, str) else args,
                },
            })
        return Message(
            role=Role.ASSISTANT,
            content=msg.get("content", "") or "",
            tool_calls=tool_calls,
        )

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

        resp = await self._client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=self._headers,
        )
        if resp.status_code != 200:
            raise LLMError(f"OpenAI returned {resp.status_code}: {resp.text}")

        if stream:
            return self._stream(resp)

        body = resp.json()
        return self._parse_reply(body["choices"][0])

    async def _stream(self, resp: httpx.Response) -> AsyncGenerator[str, None]:
        async for line in resp.aiter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                chunk = json.loads(line[6:])
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                if content := delta.get("content", ""):
                    yield content

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        payload = {
            "model": model or "text-embedding-ada-002",
            "input": text,
        }
        resp = await self._client.post(
            f"{self.base_url}/embeddings",
            json=payload,
            headers=self._headers,
        )
        if resp.status_code != 200:
            raise LLMError(f"Embedding failed: {resp.status_code}: {resp.text}")
        return resp.json()["data"][0]["embedding"]

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
