TASK = {
    "id": "task_022",
    "name": "Add config option",
    "description": "Add a 'debug' config option that controls verbose output.",
    "prompt": "Add a 'debug' parameter (default False) to the Config class in utils.py. Also add a method 'set_debug' that sets it and returns self (for chaining), and update the __init__ to accept debug as a keyword argument.",
    "files": {
        "utils.py": "class Config:\n    def __init__(self, host=\"localhost\", port=8080):\n        self.host = host\n        self.port = port\n\n    def __repr__(self):\n        return f\"Config(host={self.host}, port={self.port})\"\n"
    },
    "check": {
        "type": "python_code",
        "test": "from utils import Config\n\nc = Config()\nassert hasattr(c, 'debug'), \"Config should have debug attribute\"\nassert c.debug == False, \"debug should default to False\"\n\nc2 = Config(debug=True)\nassert c2.debug == True\n\nc3 = Config().set_debug(True)\nassert c3.debug == True\nassert c3 is c3.set_debug(False)  # chaining\n"
    }
}
