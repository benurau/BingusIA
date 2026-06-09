TASK = {
    "id": "task_003",
    "name": "Rename API",
    "description": "Rename function 'calc_total' to 'calculate_total' and update all callers.",
    "prompt": "Rename the function 'calc_total' to 'calculate_total' in utils.py and update its call site.",
    "files": {
        "utils.py": "def calc_total(prices):\n    return sum(prices)\n\ndef get_summary(prices):\n    t = calc_total(prices)\n    return f\"Total: ${t:.2f}\"\n"
    },
    "check": {
        "type": "python_code",
        "test": "from utils import calculate_total, get_summary\nassert calculate_total([10, 20, 30]) == 60\nassert get_summary([10, 20, 30]) == \"Total: $60.00\"\n"
    }
}
