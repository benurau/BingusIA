TASK = {
    "id": "task_009",
    "name": "Add error handling",
    "description": "Add try/except to handle missing files gracefully.",
    "prompt": "Add error handling to read_file_safe in utils.py. It should return the file content as a string, or return an empty string if the file doesn't exist or can't be read.",
    "files": {
        "utils.py": "def read_file_safe(path):\n    # TODO: add try/except\n    with open(path, 'r') as f:\n        return f.read()\n"
    },
    "check": {
        "type": "python_code",
        "test": "from utils import read_file_safe\nimport tempfile, os\n# Test with existing file\nwith tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:\n    f.write(\"hello world\")\n    path = f.name\nresult = read_file_safe(path)\nos.unlink(path)\nassert result == \"hello world\"\n# Test with non-existing file\nresult2 = read_file_safe(\"/nonexistent/file.txt\")\nassert result2 == \"\"\n"
    }
}
