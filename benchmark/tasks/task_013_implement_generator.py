TASK = {
    "id": "task_013",
    "name": "Implement generator",
    "description": "Make the fibonacci function a generator that yields values.",
    "prompt": "Rewrite the fibonacci function in utils.py as a generator that yields Fibonacci numbers up to n terms.",
    "files": {
        "utils.py": "def fibonacci(n):\n    # TODO: implement as generator\n    pass\n"
    },
    "check": {
        "type": "python_code",
        "test": "from utils import fibonacci\nresult = list(fibonacci(10))\nassert result == [0, 1, 1, 2, 3, 5, 8, 13, 21, 34], f\"Got {result}\"\nassert list(fibonacci(0)) == []\nassert list(fibonacci(1)) == [0]\n"
    }
}
