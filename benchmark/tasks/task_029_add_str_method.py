TASK = {
    "id": "task_029",
    "name": "Add __str__ method",
    "description": "Add a __str__ method to the Book class for a readable representation.",
    "prompt": "Add a __str__ method to the Book class in utils.py that returns a string like 'Book(title=\"The Hobbit\", author=\"Tolkien\", year=1937)'.",
    "files": {
        "utils.py": "class Book:\n    def __init__(self, title, author, year):\n        self.title = title\n        self.author = author\n        self.year = year\n"
    },
    "check": {
        "type": "python_code",
        "test": "from utils import Book\n\nb = Book(\"The Hobbit\", \"Tolkien\", 1937)\ns = str(b)\nassert \"The Hobbit\" in s\nassert \"Tolkien\" in s\nassert \"1937\" in s\nassert b.title == \"The Hobbit\"  # original attributes intact\n"
    }
}
