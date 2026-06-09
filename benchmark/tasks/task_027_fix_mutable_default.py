TASK = {
    "id": "task_027",
    "name": "Fix mutable default arg",
    "description": "Fix the mutable default argument issue ([] as default).",
    "prompt": "Fix the mutable default argument bug in add_item in utils.py. Change the default value of items from [] to None and handle it properly inside the function.",
    "files": {
        "utils.py": "def add_item(item, items=[]):\n    items.append(item)\n    return items\n"
    },
    "check": {
        "type": "python_code",
        "test": "from utils import add_item\n\n# Test that separate calls don't share state\nresult1 = add_item(\"a\")\nresult2 = add_item(\"b\")\nassert result1 == [\"a\"], f\"Expected ['a'], got {result1}\"\nassert result2 == [\"b\"], f\"Expected ['b'], got {result2}\"\n\n# Test with explicit list\nresult3 = add_item(\"c\", [\"x\", \"y\"])\nassert result3 == [\"x\", \"y\", \"c\"]\n"
    }
}
