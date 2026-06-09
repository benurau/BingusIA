TASK = {
    "id": "task_004",
    "name": "Implement TODO",
    "description": "Implement a function from a TODO comment that reads and parses a JSON config file.",
    "prompt": "Implement the TODO in utils.py. The load_config function should read a JSON file from the given path and return the parsed dict. If the file doesn't exist, return an empty dict.",
    "files": {
        "utils.py": "import json\n\ndef load_config(path):\n    # TODO: implement this function\n    pass\n"
    },
    "check": {
        "type": "python_code",
        "test": "import json, tempfile, os\nfrom utils import load_config\nwith tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:\n    json.dump({\"key\": \"value\"}, f)\n    path = f.name\nresult = load_config(path)\nos.unlink(path)\nassert result == {\"key\": \"value\"}, f\"Expected dict, got {result}\"\nassert load_config(\"/nonexistent/file.json\") == {}\n"
    }
}
