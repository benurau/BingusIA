TASK = {
    "id": "task_021",
    "name": "Move function to file",
    "description": "Move the helper function to a new file and update the import.",
    "prompt": "Move the 'helper' function from utils.py into a new file called helpers.py. Then update utils.py to import helper from helpers and expose it.",
    "files": {
        "utils.py": "def helper(name):\n    return f\"Hello, {name}!\"\n\ndef greet(name):\n    return helper(name)\n"
    },
    "check": {
        "type": "python_code",
        "test": "from utils import greet, helper\nassert greet(\"World\") == \"Hello, World!\"\nassert helper(\"Alice\") == \"Hello, Alice!\"\nimport helpers\nassert helpers.helper(\"Bob\") == \"Hello, Bob!\"\n"
    }
}
