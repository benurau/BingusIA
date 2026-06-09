TASK = {
    "id": "task_018",
    "name": "Fix failing test",
    "description": "Fix the code so that the existing test passes.",
    "prompt": "The test in test_utils.py is failing. Fix the code in utils.py so that the test passes. Do not modify the test file.",
    "files": {
        "utils.py": "def reverse_string(s):\n    result = \"\"\n    for i in range(len(s)):\n        result += s[i]\n    return result\n",
        "test_utils.py": "from utils import reverse_string\n\ndef test_reverse_string():\n    assert reverse_string(\"hello\") == \"olleh\"\n    assert reverse_string(\"abc\") == \"cba\"\n    assert reverse_string(\"\") == \"\"\n"
    },
    "check": {
        "type": "pytest",
        "test": "test_utils.py"
    }
}
