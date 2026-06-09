TASK = {
    "id": "task_015",
    "name": "Change default parameter",
    "description": "Change the default timeout from 30 to 60 seconds.",
    "prompt": "Change the default value of the 'timeout' parameter in the connect function from 30 to 60.",
    "files": {
        "utils.py": "def connect(host, port, timeout=30):\n    return {\"host\": host, \"port\": port, \"timeout\": timeout}\n"
    },
    "check": {
        "type": "python_code",
        "test": "from utils import connect\nimport inspect\nsig = inspect.signature(connect)\nassert sig.parameters['timeout'].default == 60, f\"Default should be 60, got {sig.parameters['timeout'].default}\"\nresult = connect(\"localhost\", 8080)\nassert result[\"timeout\"] == 60\n"
    }
}
