from bingus_ia.files.diff_display import unified_diff, print_diff, print_creation


class TestUnifiedDiff:
    def test_no_change(self):
        result = unified_diff("same\n", "same\n", "f.txt")
        assert result == ""

    def test_addition(self):
        result = unified_diff("a\nb\n", "a\nb\nc\n", "f.txt")
        assert "a/f.txt" in result
        assert "b/f.txt" in result
        assert "+c" in result

    def test_removal(self):
        result = unified_diff("a\nb\nc\n", "a\nc\n", "f.txt")
        assert "-b" in result

    def test_modification(self):
        result = unified_diff("hello\n", "world\n", "f.txt")
        assert "-hello" in result
        assert "+world" in result

    def test_empty_old(self):
        result = unified_diff("", "new content\n", "new.txt")
        assert "+new content" in result

    def test_empty_new(self):
        result = unified_diff("old content\n", "", "old.txt")
        assert "-old content" in result

    def test_path_format(self):
        result = unified_diff("a\n", "b\n", "src/main.py")
        assert "a/src/main.py" in result
        assert "b/src/main.py" in result

    def test_creation_output(self):
        import io, sys
        out = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = out
        try:
            print_creation("hello\nworld\n", "test.txt")
            output = out.getvalue()
            assert "Created: test.txt" in output
            assert "hello" in output
            assert "world" in output
        finally:
            sys.stdout = old_stdout

    def test_diff_output(self):
        import io, sys
        out = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = out
        try:
            print_diff("old\n", "new\n", "f.txt")
            output = out.getvalue()
            assert "-old" in output
            assert "+new" in output
        finally:
            sys.stdout = old_stdout


class TestInlineToolCallParsing:
    def _make_agent(self):
        from bingus_ia.core.agent import Agent
        from bingus_ia.core.types import AgentConfig
        import tempfile
        tmp = tempfile.mkdtemp()
        config = AgentConfig(workspace_dir=tmp, ollama_base_url="http://localhost:99999", memory_enabled=False, injection_dir=tmp)
        agent = Agent(config)
        agent.memory = None
        return agent

    def test_parse_simple_json(self):
        agent = self._make_agent()
        result = agent._parse_inline_tool_call('{"name": "read_file", "arguments": {"path": "x.txt"}}')
        assert result is not None
        assert result["function"]["name"] == "read_file"
        assert result["function"]["arguments"]["path"] == "x.txt"

    def test_parse_with_function_wrapper(self):
        agent = self._make_agent()
        result = agent._parse_inline_tool_call(
            '{"function": {"name": "write_file", "arguments": {"path": "x.txt", "content": "hi"}}}'
        )
        assert result is not None
        assert result["function"]["name"] == "write_file"
        assert result["function"]["arguments"]["content"] == "hi"

    def test_parse_with_string_arguments(self):
        agent = self._make_agent()
        result = agent._parse_inline_tool_call(
            '{"name": "write_file", "arguments": "{\\"path\\": \\"x.txt\\", \\"content\\": \\"hi\\"}"}'
        )
        assert result is not None
        assert result["function"]["name"] == "write_file"
        assert result["function"]["arguments"]["path"] == "x.txt"

    def test_parse_with_parameters_field(self):
        agent = self._make_agent()
        result = agent._parse_inline_tool_call(
            '{"name": "read_file", "parameters": {"path": "y.txt", "offset": 5}}'
        )
        assert result is not None
        assert result["function"]["arguments"]["offset"] == 5

    def test_parse_markdown_wrapped(self):
        agent = self._make_agent()
        result = agent._parse_inline_tool_call(
            '```json\n{"name": "list_dir", "arguments": {"path": "."}}\n```'
        )
        assert result is not None
        assert result["function"]["name"] == "list_dir"

    def test_parse_too_many_lines_rejected(self):
        agent = self._make_agent()
        result = agent._parse_inline_tool_call(
            "line1\nline2\nline3\nline4\nline5\nline6\nline7\n"
        )
        assert result is None

    def test_parse_invalid_json_rejected(self):
        agent = self._make_agent()
        result = agent._parse_inline_tool_call("this is not json at all")
        assert result is None

    def test_parse_missing_name_rejected(self):
        agent = self._make_agent()
        result = agent._parse_inline_tool_call('{"not_a_tool": true}')
        assert result is None

    def test_parse_empty_content(self):
        agent = self._make_agent()
        result = agent._parse_inline_tool_call("")
        assert result is None
