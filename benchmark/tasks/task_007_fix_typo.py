TASK = {
    "id": "task_007",
    "name": "Fix typo in variable",
    "description": "Fix the typo 'occured' to 'occurred' throughout the file.",
    "prompt": "Fix the variable name typo: rename all instances of 'occured' to 'occurred' in utils.py.",
    "files": {
        "utils.py": "def log_event(event_name):\n    occured = True\n    occured_at = \"2024-01-01\"\n    return {\"event\": event_name, \"occured\": occured, \"occured_at\": occured_at}\n"
    },
    "check": {
        "type": "python_code",
        "test": "from utils import log_event\nresult = log_event(\"test\")\nassert result[\"occurred\"] == True\nassert result[\"occurred_at\"] == \"2024-01-01\"\nassert \"occured\" not in str(result)\n"
    }
}
