import tempfile
from pathlib import Path

from bingus_ia.core.types import Injection
from bingus_ia.injections.registry import InjectionRegistry


class TestRuleCreation:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp()) / "injections"
        self.tmp.mkdir()
        self.registry = InjectionRegistry(str(self.tmp))

    def test_create_rule_creates_file(self):
        result = self.registry.create_rule("Use Src Dir", "Always use src/ as the base directory")
        assert "created" in result
        files = list(self.tmp.glob("*.md"))
        assert len(files) == 1
        assert "use-src-dir" in files[0].stem

    def test_create_rule_content(self):
        self.registry.create_rule("Use Src", "Always prefix paths with src/")
        f = list(self.tmp.glob("*.md"))[0]
        content = f.read_text(encoding="utf-8")
        assert "name: Use Src" in content
        assert "Always prefix paths with src/" in content
        assert "priority: 1" in content
        assert "enabled: true" in content

    def test_create_rule_loads_into_registry(self):
        self.registry.create_rule("Test Rule", "test instruction")
        assert len(self.registry.injections) == 1
        assert self.registry.injections[0].name == "Test Rule"
        assert self.registry.injections[0].enabled is True

    def test_create_rule_with_trigger(self):
        self.registry.create_rule("Test Triggered", "instruction", trigger="deploy")
        assert len(self.registry.injections) == 1
        assert self.registry.injections[0].trigger_phrase == "deploy"

    def test_create_rule_sanitizes_name(self):
        self.registry.create_rule("!!! Special @#$ Name !!!", "instruction")
        assert len(self.registry.injections) == 1
        assert "special" in self.registry.injections[0].name.lower()

    def test_create_rule_empty_name_falls_back(self):
        self.registry.create_rule("", "instruction")
        assert len(self.registry.injections) >= 1

    def test_create_rule_updates_existing(self):
        self.registry.create_rule("My Rule", "original")
        result = self.registry.create_rule("My Rule", "updated")
        assert "updated" in result
        assert len(self.registry.injections) == 1
        content = list(self.tmp.glob("*.md"))[0].read_text(encoding="utf-8")
        assert "updated" in content

    def test_rule_appears_in_match(self):
        self.registry.create_rule("Always Active", "Always do X")
        matched = self.registry.match("anything")
        names = {i.name for i in matched}
        assert "Always Active" in names

    def test_rule_matched_by_trigger(self):
        self.registry.create_rule("Deploy Rule", "Check deploy config", trigger="deploy")
        matched = self.registry.match("run deploy now")
        assert "Deploy Rule" in {i.name for i in matched}
        not_matched = self.registry.match("just reading files")
        assert "Deploy Rule" not in {i.name for i in not_matched}


class TestRuleDeletion:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp()) / "injections"
        self.tmp.mkdir()
        self.registry = InjectionRegistry(str(self.tmp))

    def test_delete_rule_by_name(self):
        self.registry.create_rule("My Rule", "instruction")
        assert len(self.registry.injections) == 1
        result = self.registry.delete_rule("My Rule")
        assert "deleted" in result
        assert len(self.registry.injections) == 0

    def test_delete_rule_case_insensitive(self):
        self.registry.create_rule("My Rule", "instruction")
        result = self.registry.delete_rule("my rule")
        assert "deleted" in result
        assert len(self.registry.injections) == 0

    def test_delete_nonexistent_rule(self):
        result = self.registry.delete_rule("Does Not Exist")
        assert "not found" in result.lower()

    def test_delete_removes_file(self):
        self.registry.create_rule("Temp Rule", "instruction")
        files_before = list(self.tmp.glob("*.md"))
        assert len(files_before) == 1
        self.registry.delete_rule("Temp Rule")
        files_after = list(self.tmp.glob("*.md"))
        assert len(files_after) == 0


class TestRuleListing:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp()) / "injections"
        self.tmp.mkdir()
        self.registry = InjectionRegistry(str(self.tmp))

    def test_list_rules_empty(self):
        assert self.registry.list_rules() == []

    def test_list_rules(self):
        self.registry.create_rule("Rule One", "instruction 1")
        self.registry.create_rule("Rule Two", "instruction 2")
        rules = self.registry.list_rules()
        assert len(rules) == 2
        names = {r.name for r in rules}
        assert "Rule One" in names
        assert "Rule Two" in names

    def test_list_rules_excludes_non_rules(self):
        content = "---\nname: Normal Injection\ntrigger: x\n---\ny\n"
        (self.tmp / "normal.md").write_text(content, encoding="utf-8")
        (self.tmp / "rule-my-rule.md").write_text("---\nname: My Rule\ntrigger: \"\"\n---\ndo stuff\n", encoding="utf-8")
        self.registry.reload()
        rules = self.registry.list_rules()
        assert "Normal Injection" not in {r.name for r in rules}
        assert "My Rule" in {r.name for r in rules}

    def test_list_rules_shows_disabled_rules(self):
        self.registry.create_rule("Rule A", "instruction")
        self.registry.disable("Rule A")
        rules = self.registry.list_rules()
        assert len(rules) == 1
        assert rules[0].enabled is False


class TestRuleToolDispatch:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp()) / "injections"
        self.tmp.mkdir()

    def _make_agent(self):
        from bingus_ia.core.agent import Agent
        from bingus_ia.core.types import AgentConfig
        config = AgentConfig(
            workspace_dir=str(self.tmp.parent),
            ollama_base_url="http://localhost:99999",
            memory_enabled=False,
            injection_dir=str(self.tmp),
        )
        agent = Agent(config)
        agent.memory = None
        return agent

    def _tool_call(self, tool_name: str, **kwargs):
        import json
        return {"function": {"name": tool_name, "arguments": json.dumps(kwargs)}}

    def test_create_rule_tool(self):
        agent = self._make_agent()
        import asyncio
        result = asyncio.run(agent._execute_tool(self._tool_call("create_rule", name="Tool Rule", instruction="work in src")))
        assert result.success
        assert "created" in result.output
        assert len(agent.injections.injections) == 1

    def test_create_rule_tool_missing_args(self):
        agent = self._make_agent()
        import asyncio
        result = asyncio.run(agent._execute_tool(self._tool_call("create_rule", name="", instruction="")))
        assert result.success

    def test_delete_rule_tool(self):
        agent = self._make_agent()
        agent.injections.create_rule("Tool Rule", "instruction")
        import asyncio
        result = asyncio.run(agent._execute_tool(self._tool_call("delete_rule", name="Tool Rule")))
        assert result.success
        assert "deleted" in result.output
        assert len(agent.injections.injections) == 0

    def test_delete_rule_tool_not_found(self):
        agent = self._make_agent()
        import asyncio
        result = asyncio.run(agent._execute_tool(self._tool_call("delete_rule", name="Does Not Exist")))
        assert result.success
        assert "not found" in result.output
