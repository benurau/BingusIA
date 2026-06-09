from bingus_ia.core.types import AgentConfig
from bingus_ia.llm.base import BaseLLMClient
from bingus_ia.llm.ollama_client import OllamaClient
from bingus_ia.llm.openai_client import OpenAIClient
from bingus_ia.llm.anthropic_client import AnthropicClient


def create_llm_client(config: AgentConfig) -> BaseLLMClient:
    provider = config.provider.lower()

    if provider == "ollama":
        return OllamaClient(
            base_url=config.ollama_base_url,
            model=config.model,
            num_ctx=config.num_ctx,
        )
    elif provider == "openai":
        return OpenAIClient(
            api_key=config.api_key,
            model=config.model,
            base_url=config.api_base_url or "https://api.openai.com/v1",
        )
    elif provider == "anthropic":
        return AnthropicClient(
            api_key=config.api_key,
            model=config.model,
            base_url=config.api_base_url or "https://api.anthropic.com/v1",
        )
    elif provider == "opencode":
        return OpenAIClient(
            api_key=config.api_key,
            model=config.model,
            base_url=config.api_base_url or "https://opencode.ai/zen/v1",
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
