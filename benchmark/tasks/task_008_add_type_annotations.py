TASK = {
    "id": "task_008",
    "name": "Add type annotations",
    "description": "Add type annotations to all function signatures.",
    "prompt": "Add type annotations to all function parameters and return values in utils.py.",
    "files": {
        "utils.py": "def greet(name, age):\n    return f\"Hello {name}, you are {age} years old\"\n\ndef add(a, b):\n    return a + b\n"
    },
    "check": {
        "type": "python_code",
        "test": "from typing import get_type_hints\nfrom utils import greet, add\n\nhints = get_type_hints(greet)\nassert hints, \"greet should have type hints\"\nassert 'name' in hints\nassert 'return' in hints\n\nhints2 = get_type_hints(add)\nassert hints2, \"add should have type hints\"\nassert 'return' in hints2\n"
    }
}
