import tempfile
from pathlib import Path

from bingus_ia.memory.blocks import MemoryBlocks, TOKEN_BUDGET, CHAR_BUDGET


class TestMemoryBlocks:
    def setup_method(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.blocks = MemoryBlocks(str(self.tmpdir))

    def test_seeds_defaults(self):
        for name in ("persona", "human", "project"):
            assert (self.tmpdir / ".bingus_memory" / f"{name}.md").exists()

    def test_list_blocks(self):
        result = self.blocks.list_blocks()
        assert result.success
        assert "persona" in result.output
        assert "human" in result.output
        assert "project" in result.output

    def test_set_block(self):
        result = self.blocks.set_block("persona", "Be helpful and concise.")
        assert result.success
        content = self.blocks.get_block("persona")
        assert "Be helpful and concise." in content

    def test_get_block_default(self):
        content = self.blocks.get_block("persona")
        assert "How the agent should behave" in content

    def test_get_block_nonexistent(self):
        content = self.blocks.get_block("nonexistent")
        assert content == ""

    def test_replace_in_block(self):
        self.blocks.set_block("human", "Name: Alice\nLanguage: Python")
        result = self.blocks.replace_in_block("human", "Alice", "Bob")
        assert result.success
        content = self.blocks.get_block("human")
        assert "Bob" in content
        assert "Python" in content

    def test_replace_in_block_not_found(self):
        result = self.blocks.replace_in_block("human", "XXXXX", "YYYYY")
        assert not result.success

    def test_replace_in_block_nonexistent(self):
        result = self.blocks.replace_in_block("nope", "a", "b")
        assert not result.success

    def test_render_for_prompt_obeys_budget(self):
        self.blocks.set_block("persona", "x" * (CHAR_BUDGET + 5000))
        rendered = self.blocks.render_for_prompt()
        assert len(rendered) <= CHAR_BUDGET + 200

    def test_render_for_prompt_includes_blocks(self):
        self.blocks.set_block("persona", "Be concise.")
        self.blocks.set_block("human", "User likes tabs.")
        rendered = self.blocks.render_for_prompt()
        assert "Be concise." in rendered
        assert "User likes tabs." in rendered

    def test_render_for_prompt_most_recent_first(self):
        self.blocks.set_block("human", "Old info")
        import time
        time.sleep(0.01)
        self.blocks.set_block("project", "New project info")
        rendered = self.blocks.render_for_prompt()
        project_pos = rendered.find("project")
        human_pos = rendered.find("human")
        assert project_pos < human_pos, "Most recently modified block should appear first"

    def test_render_for_prompt_stops_when_budget_exceeded(self):
        small = "x" * 100
        large = "y" * (CHAR_BUDGET + 100)
        self.blocks.set_block("human", small)
        self.blocks.set_block("project", large)
        rendered = self.blocks.render_for_prompt()
        assert len(rendered) <= CHAR_BUDGET + 200

    def test_persistence_across_reload(self):
        self.blocks.set_block("project", "Uses FastAPI")
        blocks2 = MemoryBlocks(str(self.tmpdir))
        content = blocks2.get_block("project")
        assert "Uses FastAPI" in content

    def test_custom_block(self):
        result = self.blocks.set_block("debug-tips", "Check logs first")
        assert result.success
        assert (self.tmpdir / ".bingus_memory" / "debug-tips.md").exists()
        result2 = self.blocks.list_blocks()
        assert "debug-tips" in result2.output

    def test_remember_exchange_appends(self):
        self.blocks.remember_exchange("hello", "hi there")
        path = self.blocks._dir / "exchange-0001.md"
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "You: hello" in content
        assert "Bingus: hi there" in content

    def test_remember_exchange_evicts_oldest(self):
        for i in range(50):
            self.blocks.remember_exchange("x" * 200, "y" * 200)
        remaining = sorted(self.blocks._dir.glob("exchange-*.md"))
        assert len(remaining) < 50

    def test_evict_old_blocks_removes_custom_blocks_over_budget(self):
        for i in range(200):
            self.blocks.set_block(f"custom-block-{i}", "x" * 200)
        self.blocks._evict_old_blocks()
        remaining = list(self.blocks._dir.glob("custom-block-*.md"))
        assert len(remaining) < 200
