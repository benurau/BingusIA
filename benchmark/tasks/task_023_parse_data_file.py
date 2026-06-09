TASK = {
    "id": "task_023",
    "name": "Parse data file",
    "description": "Parse a CSV-formatted string into a list of dicts.",
    "prompt": "Implement parse_csv in utils.py that takes a CSV string with a header row and returns a list of dicts. Example: parse_csv('name,age\\nAlice,30\\nBob,25') should return [{'name': 'Alice', 'age': '30'}, {'name': 'Bob', 'age': '25'}].",
    "files": {
        "utils.py": "def parse_csv(text):\n    # TODO: implement CSV parser\n    pass\n"
    },
    "check": {
        "type": "python_code",
        "test": "from utils import parse_csv\n\nresult = parse_csv(\"name,age\\nAlice,30\\nBob,25\")\nassert result == [{\"name\": \"Alice\", \"age\": \"30\"}, {\"name\": \"Bob\", \"age\": \"25\"}], f\"Got {result}\"\n\nresult2 = parse_csv(\"a,b,c\\n1,2,3\")\nassert result2 == [{\"a\": \"1\", \"b\": \"2\", \"c\": \"3\"}]\n\nresult3 = parse_csv(\"header\\n\")\nassert result3 == []\n"
    }
}
