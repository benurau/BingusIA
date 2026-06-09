TASK = {
    "id": "task_024",
    "name": "Add env var support",
    "description": "Read DATABASE_URL from environment variable with a fallback default.",
    "prompt": "Update get_database_url in utils.py to read from the DATABASE_URL environment variable. If not set, return the default 'sqlite:///local.db'.",
    "files": {
        "utils.py": "import os\n\ndef get_database_url():\n    # TODO: read DATABASE_URL env var\n    pass\n"
    },
    "check": {
        "type": "python_code",
        "test": "import os\nfrom utils import get_database_url\n\n# Test default\nresult = get_database_url()\nassert result == \"sqlite:///local.db\", f\"Expected default, got {result}\"\n\n# Test with env var\nos.environ[\"DATABASE_URL\"] = \"postgres://localhost/mydb\"\nresult2 = get_database_url()\nassert result2 == \"postgres://localhost/mydb\", f\"Expected env var value, got {result2}\"\ndel os.environ[\"DATABASE_URL\"]\n"
    }
}
