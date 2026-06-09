TASK = {
    "id": "task_017",
    "name": "Add edge case test",
    "description": "Add test cases for empty and single-element input.",
    "prompt": "Add test cases to test_average in test_utils.py for empty list (should return 0) and single-element list (should return that element).",
    "files": {
        "utils.py": "def average(nums):\n    if not nums:\n        return 0\n    return sum(nums) / len(nums)\n",
        "test_utils.py": "from utils import average\n\ndef test_average_normal():\n    assert average([1, 2, 3, 4, 5]) == 3.0\n"
    },
    "check": {
        "type": "pytest",
        "test": "test_utils.py"
    }
}
