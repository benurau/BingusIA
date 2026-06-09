TASK = {
    "id": "task_030",
    "name": "Handle division by zero",
    "description": "Add a safe divide function that handles zero divisor gracefully.",
    "prompt": "Modify the safe_divide function in utils.py to return None (instead of raising ZeroDivisionError) when the divisor is 0. Return the result as an int if both values are ints, otherwise float.",
    "files": {
        "utils.py": "def safe_divide(a, b):\n    return a / b\n"
    },
    "check": {
        "type": "python_code",
        "test": "from utils import safe_divide\n\nassert safe_divide(10, 2) == 5\nassert safe_divide(10, 3) == 10 / 3\nassert safe_divide(10, 0) is None\nassert safe_divide(0, 5) == 0\nassert safe_divide(-10, 2) == -5\n"
    }
}
