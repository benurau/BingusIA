TASK = {
    "id": "task_019",
    "name": "Create new module",
    "description": "Create a new module 'text_utils.py' with string helper functions and import them in utils.py.",
    "prompt": "Create a new file called text_utils.py with two functions: 'capitalize_words(s)' that capitalizes each word, and 'reverse_words(s)' that reverses the order of words. Then import both functions into utils.py and expose them so they can be imported from utils.",
    "files": {
        "utils.py": "# Import the new text_utils functions here\n"
    },
    "check": {
        "type": "python_code",
        "test": "from utils import capitalize_words, reverse_words\nassert capitalize_words(\"hello world\") == \"Hello World\"\nassert reverse_words(\"hello world\") == \"world hello\"\n"
    }
}
