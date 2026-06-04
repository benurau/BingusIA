from abc import ABC, abstractmethod
from typing import AsyncGenerator

from bingus_ia.core.types import Message


class LLMError(Exception):
    pass


class BaseLLMClient(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        stream: bool = False,
    ) -> Message | AsyncGenerator[str, None]:
        ...

    @abstractmethod
    async def embed(self, text: str, model: str | None = None) -> list[float]:
        ...

    @abstractmethod
    async def list_models(self) -> list[dict]:
        ...

    @abstractmethod
    async def close(self):
        ...
