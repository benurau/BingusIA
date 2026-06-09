import json
import os
from pathlib import Path

from bingus_ia.core.types import AgentConfig

DEFAULT_CONFIG_PATH = Path("bingus_ia_config.json")


def load_config(path: str | None = None) -> AgentConfig:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    config = AgentConfig()

    if config_path.exists():
        with open(config_path) as f:
            data = json.load(f)
        for key, value in data.items():
            if hasattr(config, key):
                setattr(config, key, value)

    env_overrides = {
        "provider": "BINGUS_PROVIDER",
        "ollama_base_url": "BINGUS_OLLAMA_URL",
        "model": "BINGUS_MODEL",
        "api_key": "BINGUS_API_KEY",
        "api_base_url": "BINGUS_API_BASE_URL",
        "workspace_dir": "BINGUS_WORKSPACE",
        "max_turns": "BINGUS_MAX_TURNS",
    }

    for attr, env_var in env_overrides.items():
        if env_var in os.environ:
            val = os.environ[env_var]
            if attr == "max_turns":
                val = int(val)
            setattr(config, attr, val)

    config.workspace_dir = str(Path(config.workspace_dir).resolve())
    return config


def save_config(config: AgentConfig, path: str | None = None) -> None:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    data = {
        "provider": config.provider,
        "ollama_base_url": config.ollama_base_url,
        "model": config.model,
        "api_key": config.api_key,
        "api_base_url": config.api_base_url,
        "workspace_dir": config.workspace_dir,
        "max_turns": config.max_turns,
        "memory_enabled": config.memory_enabled,
        "injection_dir": config.injection_dir,
        "prompt_dir": config.prompt_dir,
        "embedding_model": config.embedding_model,
    }
    with open(config_path, "w") as f:
        json.dump(data, f, indent=2)
