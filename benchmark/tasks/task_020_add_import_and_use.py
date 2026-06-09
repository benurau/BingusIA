TASK = {
    "id": "task_020",
    "name": "Add import and use",
    "description": "Add json import and use it to serialize the result.",
    "prompt": "Add an import for the 'json' module at the top of utils.py and modify get_data to return the dict as a JSON string using json.dumps.",
    "files": {
        "utils.py": "def get_data():\n    return {\"name\": \"Alice\", \"age\": 30}\n"
    },
    "check": {
        "type": "python_code",
        "test": "from utils import get_data\nimport json\nresult = get_data()\nparsed = json.loads(result)\nassert parsed == {\"name\": \"Alice\", \"age\": 30}\n"
    }
}
