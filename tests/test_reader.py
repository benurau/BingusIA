import tempfile
from pathlib import Path

from bingus_ia.files.reader import FileReader


class TestFileReader:
    def setup_method(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.reader = FileReader(str(self.tmpdir))

    def test_list_dir_empty(self):
        result = self.reader.list_dir(".")
        assert result.success is True
        assert result.output == ""

    def test_list_dir_with_files(self):
        (self.tmpdir / "a.txt").write_text("a")
        (self.tmpdir / "b.py").write_text("b")
        (self.tmpdir / "sub").mkdir()
        result = self.reader.list_dir(".")
        assert result.success is True
        lines = result.output.split("\n")
        assert "a.txt" in lines
        assert "b.py" in lines
        assert "sub/" in lines

    def test_read_file(self):
        f = self.tmpdir / "hello.txt"
        f.write_text("line1\nline2\nline3\n")
        result = self.reader.read_file("hello.txt")
        assert result.success is True
        assert "line1" in result.output
        assert "line2" in result.output
        assert "hello.txt" in result.output

    def test_read_file_with_offset(self):
        f = self.tmpdir / "hello.txt"
        f.write_text("line1\nline2\nline3\n")
        result = self.reader.read_file("hello.txt", offset=1, limit=1)
        assert result.success is True
        assert "line2" in result.output
        assert "line1" not in result.output

    def test_read_nonexistent(self):
        result = self.reader.read_file("nope.txt")
        assert result.success is False
        assert result.error is not None

    def test_read_outside_workspace(self):
        result = self.reader.read_file(str(Path(tempfile.gettempdir()) / "secret.txt"))
        assert result.success is False

    def test_list_dir_outside_workspace(self):
        result = self.reader.list_dir(str(Path(tempfile.gettempdir())))
        assert result.success is False

    def test_set_workspace(self):
        tmp2 = Path(tempfile.mkdtemp())
        self.reader.set_workspace(str(tmp2))
        assert self.reader.workspace == tmp2.resolve()
        (tmp2 / "new.txt").write_text("in new ws")
        result = self.reader.read_file("new.txt")
        assert result.success
        assert "in new ws" in result.output
