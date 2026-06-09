TASK = {
    "id": "task_001",
    "name": "Add optional parameter",
    "description": "Add an optional 'reverse' parameter (default False) to the sort_items function that reverses the order when True.",
    "prompt": "Add an optional 'reverse' parameter (default False) to the sort_items function in utils.py. When reverse=True, the list should be sorted in descending order.",
    "files": {
        "utils.py": "def sort_items(items):\n    return sorted(items)\n"
    },
    "check": {
        "type": "python_code",
        "test": "from utils import sort_items\nassert sort_items([3, 1, 2]) == [1, 2, 3]\nassert sort_items([3, 1, 2], reverse=True) == [3, 2, 1]\nassert sort_items([3, 1, 2], reverse=False) == [1, 2, 3]\n"
    }
}
