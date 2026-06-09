TASK = {
    "id": "task_010",
    "name": "Fix logic error",
    "description": "Fix incorrect use of 'and' instead of 'or' in validation logic.",
    "prompt": "Fix the logic error in is_valid_password in utils.py. A valid password should be longer than 8 characters OR contain a number (not both required).",
    "files": {
        "utils.py": "def is_valid_password(password):\n    has_number = any(c.isdigit() for c in password)\n    long_enough = len(password) > 8\n    return long_enough and has_number\n"
    },
    "check": {
        "type": "python_code",
        "test": "from utils import is_valid_password\nassert is_valid_password(\"short1\") == False\nassert is_valid_password(\"longenough\") == True\nassert is_valid_password(\"short123\") == True\nassert is_valid_password(\"short\") == False\n"
    }
}
