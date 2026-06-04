import asyncio
import json
import tempfile
from pathlib import Path

from bingus_ia.core.agent import Agent
from bingus_ia.core.types import AgentConfig


def _make_agent() -> Agent:
    tmp = Path(tempfile.mkdtemp())
    config = AgentConfig(workspace_dir=str(tmp), ollama_base_url="http://localhost:99999", memory_enabled=False)
    agent = Agent(config)
    agent.memory = None
    return agent


def _tool_call(tool_name: str, **kwargs) -> dict:
    return {
        "function": {
            "name": tool_name,
            "arguments": json.dumps(kwargs),
        }
    }


def _exec(agent: Agent, tc: dict):
    return asyncio.run(agent._execute_tool(tc))


class TestAgentMemoryBlocks:
    def test_memory_block_list(self):
        agent = _make_agent()
        result = _exec(agent, _tool_call("memory_block_list"))
        assert result.success
        assert "persona" in result.output

    def test_memory_block_set(self):
        agent = _make_agent()
        result = _exec(agent, _tool_call("memory_block_set", name="human", content="Test user"))
        assert result.success
        result2 = _exec(agent, _tool_call("memory_block_list"))
        assert "Test user" in result2.output or "human" in result2.output

    def test_memory_block_replace(self):
        agent = _make_agent()
        _exec(agent, _tool_call("memory_block_set", name="human", content="Name: Alice"))
        result = _exec(agent, _tool_call("memory_block_replace", name="human", old_string="Alice", new_string="Bob"))
        assert result.success
        content = agent.blocks.get_block("human")
        assert "Bob" in content

    def test_memory_block_replace_not_found(self):
        agent = _make_agent()
        result = _exec(agent, _tool_call("memory_block_replace", name="human", old_string="XXXX", new_string="YYYY"))
        assert not result.success

    def test_web_search_dispatches(self):
        agent = _make_agent()
        result = _exec(agent, _tool_call("web_search", query="", num_results=1))
        assert not result.success or "No results" in result.output

    def test_render_for_prompt_in_system(self):
        agent = _make_agent()
        agent.blocks.set_block("persona", "Be terse.")
        rendered = agent.blocks.render_for_prompt()
        assert "Be terse." in rendered

    def test_web_fetch_dispatches(self):
        agent = _make_agent()
        result = _exec(agent, _tool_call("web_fetch", url=""))
        assert not result.success
