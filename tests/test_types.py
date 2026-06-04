from bingus_ia.core.types import Injection, Message, Role, ToolResult, ToolName


class TestInjection:
    def test_defaults(self):
        inj = Injection(name="x", trigger_phrase="y", prompt_override="z")
        assert inj.name == "x"
        assert inj.trigger_phrase == "y"
        assert inj.prompt_override == "z"
        assert inj.priority == 0
        assert inj.enabled is True
        assert inj.urls == []

    def test_with_urls(self):
        inj = Injection(name="x", trigger_phrase="y", prompt_override="z", urls=["https://a.com", "https://b.com"])
        assert len(inj.urls) == 2
        assert inj.urls[0] == "https://a.com"

    def test_disabled(self):
        inj = Injection(name="x", trigger_phrase="y", prompt_override="z", enabled=False)
        assert inj.enabled is False


class TestMessage:
    def test_system_message(self):
        m = Message(role=Role.SYSTEM, content="be helpful")
        assert m.role == Role.SYSTEM
        assert m.content == "be helpful"

    def test_with_tool_calls(self):
        m = Message(role=Role.ASSISTANT, content="", tool_calls=[{"function": {"name": "read_file"}}])
        assert len(m.tool_calls) == 1


class TestToolResult:
    def test_success(self):
        r = ToolResult(ToolName.READ_FILE, True, output="file content")
        assert r.success is True
        assert r.output == "file content"
        assert r.error is None

    def test_error(self):
        r = ToolResult(ToolName.EDIT_FILE, False, output="", error="file not found")
        assert r.success is False
        assert r.error == "file not found"
