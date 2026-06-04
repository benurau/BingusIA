from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Role(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolName(Enum):
    READ_FILE = "read_file"
    EDIT_FILE = "edit_file"
    LIST_DIR = "list_dir"
    SEARCH_CODE = "search_code"
    MEMORY_LOOKUP = "memory_lookup"
    MEMORY_STORE = "memory_store"
    RUN_COMMAND = "run_command"
    SET_WORKSPACE = "set_workspace"
    MEMORY_BLOCK_LIST = "memory_block_list"
    MEMORY_BLOCK_SET = "memory_block_set"
    MEMORY_BLOCK_REPLACE = "memory_block_replace"
    WEB_SEARCH = "web_search"
    WEB_FETCH = "web_fetch"
    RUN_TERMINAL = "run_terminal"


class LLMProvider(Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENCODE = "opencode"


@dataclass
class Message:
    role: Role
    content: str
    tool_calls: list[dict] = field(default_factory=list)
    tool_call_id: str = ""


@dataclass
class ToolResult:
    tool: ToolName
    success: bool
    output: str
    error: Optional[str] = None


@dataclass
class MemoryEntry:
    id: str
    prompt: str
    response: str
    timestamp: float
    embedding: list[float] | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Injection:
    name: str
    trigger_phrase: str
    prompt_override: str
    priority: int = 0
    enabled: bool = True
    urls: list[str] = field(default_factory=list)


@dataclass
class AgentConfig:
    provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    model: str = "codellama:7b"
    api_key: str = ""
    api_base_url: str = ""
    workspace_dir: str = "."
    max_turns: int = 25
    memory_enabled: bool = True
    injection_dir: str = "injections"
    embedding_model: str = "nomic-embed-text"
    system_prompt: str = ""
