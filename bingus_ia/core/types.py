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
    WRITE_FILE = "write_file"


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
class AgentConfig:
    provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    model: str = "codellama:7b"
    api_key: str = ""
    api_base_url: str = ""
    workspace_dir: str = "."
    max_turns: int = 10
    num_ctx: int = 8192
    system_prompt: str = ""
