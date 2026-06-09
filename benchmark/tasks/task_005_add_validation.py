TASK = {
    "id": "task_005",
    "name": "Add validation",
    "description": "Add input validation to ensure age is a positive integer.",
    "prompt": "Add validation to set_age in utils.py. It should raise a ValueError if age is not a positive integer (less than or equal to 0, or not an int).",
    "files": {
        "utils.py": "class Person:\n    def __init__(self):\n        self._age = 0\n\n    def set_age(self, age):\n        self._age = age\n\n    def get_age(self):\n        return self._age\n"
    },
    "check": {
        "type": "python_code",
        "test": "from utils import Person\np = Person()\np.set_age(25)\nassert p.get_age() == 25\n\ntry:\n    p.set_age(-5)\n    assert False, \"Should raise ValueError\"\nexcept ValueError:\n    pass\n\ntry:\n    p.set_age(0)\n    assert False, \"Should raise ValueError\"\nexcept ValueError:\n    pass\n\ntry:\n    p.set_age(\"25\")\n    assert False, \"Should raise ValueError\"\nexcept ValueError:\n    pass\n"
    }
}
