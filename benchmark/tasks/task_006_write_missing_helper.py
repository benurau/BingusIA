TASK = {
    "id": "task_006",
    "name": "Write missing helper",
    "description": "Complete the format_date function to format a date as 'YYYY-MM-DD'.",
    "prompt": "Complete the format_date function in utils.py. It should take a datetime object and return a string formatted as 'YYYY-MM-DD'.",
    "files": {
        "utils.py": "from datetime import datetime\n\ndef format_date(dt):\n    # TODO: return date formatted as YYYY-MM-DD\n    pass\n"
    },
    "check": {
        "type": "python_code",
        "test": "from datetime import datetime\nfrom utils import format_date\ndt = datetime(2024, 3, 15, 10, 30, 0)\nresult = format_date(dt)\nassert result == \"2024-03-15\", f\"Expected '2024-03-15', got '{result}'\"\n"
    }
}
