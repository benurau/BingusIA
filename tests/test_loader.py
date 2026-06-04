from pathlib import Path

from bingus_ia.injections.loader import InjectionLoader

FIXTURES = Path(__file__).parent / "fixtures"


class TestInjectionLoader:
    def setup_method(self):
        self.loader = InjectionLoader(str(FIXTURES))

    def test_load_all(self):
        injections = self.loader.load_all()
        names = {i.name for i in injections}
        assert "Test Injection" in names
        assert "Blocked Injection" in names
        assert "no_frontmatter" in names
        assert "Disabled Injection" in names

    def test_parse_frontmatter(self):
        injections = self.loader.load_all()
        test_inj = next(i for i in injections if i.name == "Test Injection")
        assert test_inj.trigger_phrase == "test"
        assert test_inj.priority == 5
        assert test_inj.enabled is True
        assert "https://example.com" in test_inj.urls
        assert "https://httpbin.org/get" in test_inj.urls

    def test_parse_no_frontmatter(self):
        injections = self.loader.load_all()
        no_fm = next(i for i in injections if i.name == "no_frontmatter")
        assert no_fm.trigger_phrase == ""
        assert no_fm.priority == 0
        assert no_fm.enabled is True
        assert no_fm.urls == []

    def test_disabled_injection(self):
        injections = self.loader.load_all()
        disabled = next(i for i in injections if i.name == "Disabled Injection")
        assert disabled.enabled is False
        assert disabled.trigger_phrase == "disabled"

    def test_priority_ordering(self):
        injections = self.loader.load_all()
        priorities = [i.priority for i in injections]
        assert priorities == sorted(priorities, reverse=True)

    def test_match_by_trigger(self):
        injections = self.loader.load_all()
        matched = self.loader.match("run a test please", injections)
        names = {i.name for i in matched}
        assert "Test Injection" in names
        assert "no_frontmatter" in names
        assert "Disabled Injection" not in names

    def test_match_no_frontmatter_always_included(self):
        injections = self.loader.load_all()
        matched = self.loader.match("something random", injections)
        names = {i.name for i in matched}
        assert "no_frontmatter" in names

    def test_escape_trigger_regex(self):
        injections = self.loader.load_all()
        matched = self.loader.match("rm -rf something", injections)
        names = {i.name for i in matched}
        assert "Blocked Injection" in names

    def test_empty_dir(self):
        empty_loader = InjectionLoader(str(FIXTURES / "nonexistent"))
        assert empty_loader.load_all() == []
