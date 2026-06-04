import tempfile
from pathlib import Path

from bingus_ia.files.editor import FileEditor


class TestFileEditor:
    def setup_method(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.editor = FileEditor(str(self.tmpdir))

    def test_edit_file(self):
        f = self.tmpdir / "hello.txt"
        f.write_text("foo bar baz")
        result = self.editor.edit_file("hello.txt", "bar", "qux")
        assert result.success is True
        assert f.read_text() == "foo qux baz"

    def test_edit_nonexistent(self):
        result = self.editor.edit_file("nope.txt", "a", "b")
        assert result.success is False

    def test_edit_string_not_found(self):
        f = self.tmpdir / "hello.txt"
        f.write_text("abc")
        result = self.editor.edit_file("hello.txt", "xyz", "def")
        assert result.success is False
        assert "not found" in result.error

    def test_edit_multiple_matches(self):
        f = self.tmpdir / "hello.txt"
        f.write_text("a a a")
        result = self.editor.edit_file("hello.txt", "a", "b")
        assert result.success is False
        assert "Multiple matches" in result.error

    def test_write_file(self):
        result = self.editor.write_file("new.txt", "hello world")
        assert result.success is True
        f = self.tmpdir / "new.txt"
        assert f.read_text() == "hello world"

    def test_write_file_creates_dirs(self):
        result = self.editor.write_file("a/b/c/deep.txt", "deep")
        assert result.success is True
        f = self.tmpdir / "a" / "b" / "c" / "deep.txt"
        assert f.read_text() == "deep"

    def test_write_outside_workspace(self):
        result = self.editor.write_file(str(Path(tempfile.gettempdir()) / "escape.txt"), "x")
        assert result.success is False

    def test_edit_empty_old_string_appends(self):
        f = self.tmpdir / "hello.txt"
        f.write_text("hello")
        result = self.editor.edit_file("hello.txt", "", " world")
        assert result.success is True
        assert f.read_text() == "hello world"

    def test_edit_empty_old_string_creates_file(self):
        result = self.editor.edit_file("new.txt", "", "new content")
        assert result.success is True
        f = self.tmpdir / "new.txt"
        assert f.read_text() == "new content"

    def test_set_workspace(self):
        tmp2 = Path(tempfile.mkdtemp())
        self.editor.set_workspace(str(tmp2))
        assert self.editor.workspace == tmp2.resolve()
        result = self.editor.write_file("moved.txt", "moved content")
        assert result.success
        assert (tmp2 / "moved.txt").read_text(encoding="utf-8") == "moved content"
