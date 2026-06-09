TASK = {
    "id": "task_014",
    "name": "Refactor to helper",
    "description": "Extract duplicate code into a helper function.",
    "prompt": "Extract the duplicate area calculation in utils.py into a helper function called _circle_area, then use it in both circle_area and circle_area_diameter.",
    "files": {
        "utils.py": "import math\n\ndef circle_area(radius):\n    return math.pi * radius ** 2\n\ndef circle_area_diameter(diameter):\n    radius = diameter / 2\n    return math.pi * radius ** 2\n"
    },
    "check": {
        "type": "python_code",
        "test": "from utils import circle_area, circle_area_diameter, _circle_area\nassert _circle_area(1) == circle_area(1)\nassert circle_area(2) == circle_area_diameter(4)\nassert abs(circle_area(2) - 12.566) < 0.01\n"
    }
}
