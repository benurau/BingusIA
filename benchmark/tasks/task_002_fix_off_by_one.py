TASK = {
    "id": "task_002",
    "name": "Fix off-by-one bug",
    "description": "Fix off-by-one error in loop that causes IndexError.",
    "prompt": "Fix the off-by-one bug in the loop in utils.py. The function should compare adjacent pairs without going out of bounds.",
    "files": {
        "utils.py": "def has_adjacent_duplicates(items):\n    for i in range(len(items)):\n        if items[i] == items[i + 1]:\n            return True\n    return False\n"
    },
    "check": {
        "type": "python_code",
        "test": "from utils import has_adjacent_duplicates\nassert has_adjacent_duplicates([1, 2, 2, 3]) == True\nassert has_adjacent_duplicates([1, 2, 3, 4]) == False\nassert has_adjacent_duplicates([]) == False\nassert has_adjacent_duplicates([1]) == False\n"
    }
}
