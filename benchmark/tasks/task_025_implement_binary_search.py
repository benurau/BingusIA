TASK = {
    "id": "task_025",
    "name": "Implement binary search",
    "description": "Implement binary search algorithm on a sorted list.",
    "prompt": "Implement binary_search in utils.py that takes a sorted list and a target value, and returns the index if found, or -1 if not found.",
    "files": {
        "utils.py": "def binary_search(items, target):\n    # TODO: implement binary search\n    pass\n"
    },
    "check": {
        "type": "python_code",
        "test": "from utils import binary_search\n\nassert binary_search([1, 3, 5, 7, 9], 5) == 2\nassert binary_search([1, 3, 5, 7, 9], 1) == 0\nassert binary_search([1, 3, 5, 7, 9], 9) == 4\nassert binary_search([1, 3, 5, 7, 9], 4) == -1\nassert binary_search([], 5) == -1\nassert binary_search([1], 1) == 0\n"
    }
}
