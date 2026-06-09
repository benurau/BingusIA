TASK = {
    "id": "task_016",
    "name": "Write unit test",
    "description": "Write a pytest test for the is_prime function.",
    "prompt": "Write a pytest test file called test_utils.py that tests the is_prime function. Test at least: primes (2, 3, 5, 7, 11), non-primes (4, 6, 8, 9, 10), and edge cases (0, 1).",
    "files": {
        "utils.py": "def is_prime(n):\n    if n < 2:\n        return False\n    for i in range(2, int(n ** 0.5) + 1):\n        if n % i == 0:\n            return False\n    return True\n"
    },
    "check": {
        "type": "pytest",
        "test": "test_utils.py",
        "setup": "from utils import is_prime\n"
    }
}
