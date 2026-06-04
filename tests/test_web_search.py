from bingus_ia.tools.web_search import WebSearch
from bingus_ia.core.types import ToolName


class TestWebSearch:
    def setup_method(self):
        self.search = WebSearch()

    def test_empty_query_returns_error(self):
        result = self.search.search("")
        assert result.tool == ToolName.WEB_SEARCH
        assert not result.success

    def test_extract_text_strips_html(self):
        html = "<html><body><h1>Title</h1><p>Hello world</p></body></html>"
        text = self.search._extract_text(html)
        assert "Title" in text
        assert "Hello world" in text
        assert "<h1>" not in text

    def test_extract_text_removes_scripts(self):
        html = "<html><script>alert('x')</script><body>Content</body></html>"
        text = self.search._extract_text(html)
        assert "alert" not in text
        assert "Content" in text

    def test_fetch_invalid_url_returns_error(self):
        result = self.search.fetch("http://not-a-real-domain-12345.xyz/page")
        assert not result.success

    def test_fetch_empty_url_returns_error(self):
        result = self.search.fetch("")
        assert not result.success

    def test_search_returns_correct_tool_name(self):
        result = self.search.search("python")
        assert result.tool == ToolName.WEB_SEARCH

    def test_fetch_returns_correct_tool_name(self):
        result = self.search.fetch("")
        assert result.tool == ToolName.WEB_FETCH

    def teardown_method(self):
        self.search.close()
