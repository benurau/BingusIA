TASK = {
    "id": "task_026",
    "name": "Add caching",
    "description": "Add lru_cache decorator to memoize the fibonacci function.",
    "prompt": "Add the @functools.lru_cache decorator to the fibonacci function in utils.py to cache results.",
    "files": {
        "utils.py": "def fibonacci(n):\n    if n < 2:\n        return n\n    return fibonacci(n - 1) + fibonacci(n - 2)\n"
    },
    "check": {
        "type": "python_code",
        "test": "from utils import fibonacci\n# Should compute quickly even for large n with caching\nresult = fibonacci(100)\nassert result == 354224848179261915075, f\"Got {result}\"\nassert fibonacci(0) == 0\nassert fibonacci(1) == 1\n"
    }
}
