TASK = {
    "id": "task_028",
    "name": "Add null check",
    "description": "Add a None check before accessing object attributes.",
    "prompt": "Add a null check to get_user_email in utils.py. If the user object is None, return 'anonymous@unknown.com'. Otherwise return user.email.",
    "files": {
        "utils.py": "class User:\n    def __init__(self, email):\n        self.email = email\n\ndef get_user_email(user):\n    return user.email\n"
    },
    "check": {
        "type": "python_code",
        "test": "from utils import User, get_user_email\n\nu = User(\"alice@example.com\")\nassert get_user_email(u) == \"alice@example.com\"\nassert get_user_email(None) == \"anonymous@unknown.com\"\n"
    }
}
