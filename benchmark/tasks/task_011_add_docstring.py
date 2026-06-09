TASK = {
    "id": "task_011",
    "name": "Add docstring",
    "description": "Add a descriptive docstring to the function.",
    "prompt": "Add a docstring to the calculate_bmi function in utils.py explaining what it does, its parameters, and return value.",
    "files": {
        "utils.py": "def calculate_bmi(weight_kg, height_m):\n    return weight_kg / (height_m ** 2)\n"
    },
    "check": {
        "type": "python_code",
        "test": "from utils import calculate_bmi\ndoc = calculate_bmi.__doc__\nassert doc is not None and len(doc) > 20, \"Function should have a meaningful docstring\"\nassert calculate_bmi(70, 1.75) == 70 / (1.75 ** 2)\n"
    }
}
