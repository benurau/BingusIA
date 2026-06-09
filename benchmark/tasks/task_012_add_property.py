TASK = {
    "id": "task_012",
    "name": "Add property to class",
    "description": "Add an 'email' property with getter and setter to the User class.",
    "prompt": "Add an 'email' property to the User class in utils.py with a getter and setter. The setter should validate that the email contains an '@' symbol, raising ValueError if not.",
    "files": {
        "utils.py": "class User:\n    def __init__(self, username):\n        self.username = username\n        self._email = \"\"\n"
    },
    "check": {
        "type": "python_code",
        "test": "from utils import User\nu = User(\"alice\")\nu.email = \"alice@example.com\"\nassert u.email == \"alice@example.com\"\ntry:\n    u.email = \"invalid\"\n    assert False, \"Should raise ValueError\"\nexcept ValueError:\n    pass\n"
    }
}
