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


def _tool_call(name: str, **kwargs) -> dict:
    return {
        "function": {
            "name": name,
            "arguments": json.dumps(kwargs),
        }
    }


def _exec(agent: Agent, tc: dict):
    return asyncio.run(agent._execute_tool(tc))


class TestAgentToolDispatch:
    def test_read_file(self):
        agent = _make_agent()
        f = Path(agent.config.workspace_dir) / "test.txt"
        f.write_text("hello world", encoding="utf-8")
        result = _exec(agent, _tool_call("read_file", path="test.txt"))
        assert result.success
        assert "hello world" in result.output
        assert result.tool.name == "READ_FILE"

    def test_read_file_with_offset(self):
        agent = _make_agent()
        f = Path(agent.config.workspace_dir) / "test.txt"
        f.write_text("a\nb\nc\n", encoding="utf-8")
        result = _exec(agent, _tool_call("read_file", path="test.txt", offset=1, limit=1))
        assert result.success
        assert "b" in result.output
        assert "a" not in result.output

    def test_read_file_not_found(self):
        agent = _make_agent()
        result = _exec(agent, _tool_call("read_file", path="nope.txt"))
        assert not result.success
        assert result.error is not None

    def test_edit_file(self):
        agent = _make_agent()
        f = Path(agent.config.workspace_dir) / "test.txt"
        f.write_text("foo bar baz", encoding="utf-8")
        result = _exec(agent, _tool_call("edit_file", path="test.txt", old_string="bar", new_string="qux"))
        assert result.success
        assert f.read_text(encoding="utf-8") == "foo qux baz"
        assert result.tool.name == "EDIT_FILE"

    def test_edit_file_not_found(self):
        agent = _make_agent()
        result = _exec(agent, _tool_call("edit_file", path="nope.txt", old_string="a", new_string="b"))
        assert not result.success

    def test_edit_file_multiple_matches(self):
        agent = _make_agent()
        f = Path(agent.config.workspace_dir) / "test.txt"
        f.write_text("a a a", encoding="utf-8")
        result = _exec(agent, _tool_call("edit_file", path="test.txt", old_string="a", new_string="b"))
        assert not result.success
        assert "Multiple matches" in result.error

    def test_write_file(self):
        agent = _make_agent()
        result = _exec(agent, _tool_call("write_file", path="new.txt", content="written"))
        assert result.success
        f = Path(agent.config.workspace_dir) / "new.txt"
        assert f.read_text(encoding="utf-8") == "written"
        assert result.tool.name == "EDIT_FILE"

    def test_write_file_creates_dirs(self):
        agent = _make_agent()
        result = _exec(agent, _tool_call("write_file", path="a/b/c/deep.txt", content="deep"))
        assert result.success
        assert (Path(agent.config.workspace_dir) / "a" / "b" / "c" / "deep.txt").read_text(encoding="utf-8") == "deep"

    def test_list_dir(self):
        agent = _make_agent()
        wd = Path(agent.config.workspace_dir)
        (wd / "a.txt").write_text("", encoding="utf-8")
        (wd / "sub").mkdir()
        result = _exec(agent, _tool_call("list_dir", path="."))
        assert result.success
        lines = result.output.split("\n")
        assert "a.txt" in lines
        assert "sub/" in lines
        assert result.tool.name == "LIST_DIR"

    def test_list_dir_outside_workspace_fails(self):
        agent = _make_agent()
        result = _exec(agent, _tool_call("list_dir", path=str(Path(tempfile.gettempdir()))))
        assert not result.success

    def test_search_code_returns_no_matches_when_no_ripgrep(self):
        agent = _make_agent()
        result = _exec(agent, _tool_call("search_code", pattern="something"))
        assert result.tool.name == "SEARCH_CODE"
        assert not result.success or "No matches" in result.output or "No matches" in (result.error or "")

    def test_memory_lookup_returns_disabled_message(self):
        agent = _make_agent()
        agent.memory = None
        result = _exec(agent, _tool_call("memory_lookup", query="test"))
        assert not result.success
        assert "disabled" in result.error.lower()

    def test_memory_list_returns_disabled_message(self):
        agent = _make_agent()
        agent.memory = None
        result = _exec(agent, _tool_call("memory_list"))
        assert not result.success
        assert "disabled" in result.error.lower()

    def test_unknown_tool(self):
        agent = _make_agent()
        result = _exec(agent, _tool_call("nonexistent_tool"))
        assert not result.success
        assert "Unknown" in result.error

    def test_tool_name_enum_correctness(self):
        from bingus_ia.core.types import ToolName
        assert ToolName.READ_FILE.value == "read_file"
        assert ToolName.EDIT_FILE.value == "edit_file"
        assert ToolName.LIST_DIR.value == "list_dir"
        assert ToolName.SEARCH_CODE.value == "search_code"
        assert ToolName.MEMORY_LOOKUP.value == "memory_lookup"
        assert ToolName.MEMORY_STORE.value == "memory_store"

    def test_arguments_as_dict_not_string(self):
        agent = _make_agent()
        f = Path(agent.config.workspace_dir) / "test.txt"
        f.write_text("hello", encoding="utf-8")
        tc = {
            "function": {
                "name": "read_file",
                "arguments": {"path": "test.txt"},
            }
        }
        result = _exec(agent, tc)
        assert result.success
        assert "hello" in result.output

    def test_edit_file_empty_old_string_appends(self):
        agent = _make_agent()
        f = Path(agent.config.workspace_dir) / "test.txt"
        f.write_text("content", encoding="utf-8")
        result = _exec(agent, _tool_call("edit_file", path="test.txt", old_string="", new_string="x"))
        assert result.success
        assert f.read_text(encoding="utf-8") == "contentx"

    def test_edit_file_empty_old_string_creates_file(self):
        agent = _make_agent()
        f = Path(agent.config.workspace_dir) / "new.txt"
        result = _exec(agent, _tool_call("edit_file", path="new.txt", old_string="", new_string="created"))
        assert result.success
        assert f.read_text(encoding="utf-8") == "created"


class TestToolEdgeCases:
    def test_edit_file_no_change(self):
        agent = _make_agent()
        f = Path(agent.config.workspace_dir) / "test.txt"
        f.write_text("abc", encoding="utf-8")
        result = _exec(agent, _tool_call("edit_file", path="test.txt", old_string="abc", new_string="abc"))
        assert result.success
        assert f.read_text(encoding="utf-8") == "abc"

    def test_list_dir_deeply_nested(self):
        agent = _make_agent()
        wd = Path(agent.config.workspace_dir)
        (wd / "a" / "b" / "c").mkdir(parents=True)
        (wd / "a" / "f1.txt").write_text("", encoding="utf-8")
        result = _exec(agent, _tool_call("list_dir", path="a"))
        assert result.success
        assert "b/" in result.output
        assert "f1.txt" in result.output

    def test_read_file_beyond_end(self):
        agent = _make_agent()
        f = Path(agent.config.workspace_dir) / "test.txt"
        f.write_text("a\nb\n", encoding="utf-8")
        result = _exec(agent, _tool_call("read_file", path="test.txt", offset=100, limit=10))
        assert result.success

    def test_write_empty_content(self):
        agent = _make_agent()
        result = _exec(agent, _tool_call("write_file", path="empty.txt", content=""))
        assert result.success
        assert (Path(agent.config.workspace_dir) / "empty.txt").read_text(encoding="utf-8") == ""

    def test_list_dir_root(self):
        agent = _make_agent()
        result = _exec(agent, _tool_call("list_dir"))
        assert result.success

    def test_list_dir_empty(self):
        agent = _make_agent()
        result = _exec(agent, _tool_call("list_dir", path="."))
        assert result.success

    def test_read_file_empty(self):
        agent = _make_agent()
        f = Path(agent.config.workspace_dir) / "empty.txt"
        f.write_text("", encoding="utf-8")
        result = _exec(agent, _tool_call("read_file", path="empty.txt"))
        assert result.success

    def test_read_large_file(self):
        agent = _make_agent()
        f = Path(agent.config.workspace_dir) / "large.txt"
        f.write_text("\n".join(f"line{i}" for i in range(500)), encoding="utf-8")
        result = _exec(agent, _tool_call("read_file", path="large.txt"))
        assert result.success
        assert "line0" in result.output
        assert f"({Path(f.name)}" in result.output or "large.txt" in result.output

    def test_write_and_read_back(self):
        agent = _make_agent()
        _exec(agent, _tool_call("write_file", path="roundtrip.txt", content="round trip test"))
        result = _exec(agent, _tool_call("read_file", path="roundtrip.txt"))
        assert result.success
        assert "round trip test" in result.output

    def test_edit_and_read_back(self):
        agent = _make_agent()
        _exec(agent, _tool_call("write_file", path="editme.txt", content="before"))
        _exec(agent, _tool_call("edit_file", path="editme.txt", old_string="before", new_string="after"))
        result = _exec(agent, _tool_call("read_file", path="editme.txt"))
        assert result.success
        assert "after" in result.output


class TestWorkspaceSwitching:
    def test_set_workspace_creates_dir(self):
        agent = _make_agent()
        new_dir = Path(tempfile.mkdtemp()) / "new_workspace"
        result = _exec(agent, _tool_call("set_workspace", path=str(new_dir)))
        assert result.success
        assert new_dir.is_dir()
        assert agent.config.workspace_dir == str(new_dir.resolve())
        assert agent.reader.workspace == new_dir.resolve()
        assert agent.editor.workspace == new_dir.resolve()

    def test_set_workspace_persists_writes(self):
        agent = _make_agent()
        new_dir = Path(tempfile.mkdtemp()) / "persist_ws"
        _exec(agent, _tool_call("set_workspace", path=str(new_dir)))
        _exec(agent, _tool_call("write_file", path="after_move.txt", content="hello"))
        assert (new_dir / "after_move.txt").read_text(encoding="utf-8") == "hello"

    def test_set_workspace_persists_reads(self):
        agent = _make_agent()
        new_dir = Path(tempfile.mkdtemp()) / "persist_ws2"
        new_dir.mkdir(parents=True)
        (new_dir / "existing.txt").write_text("works")
        _exec(agent, _tool_call("set_workspace", path=str(new_dir)))
        result = _exec(agent, _tool_call("read_file", path="existing.txt"))
        assert result.success
        assert "works" in result.output

    def test_old_workspace_inaccessible(self):
        agent = _make_agent()
        old_dir = Path(agent.config.workspace_dir)
        new_dir = Path(tempfile.mkdtemp()) / "locked_ws"
        _exec(agent, _tool_call("set_workspace", path=str(new_dir)))
        result = _exec(agent, _tool_call("write_file", path=str(old_dir / "sneaky.txt"), content="nope"))
        assert not result.success
