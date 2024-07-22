class User:
    def __init__(self, id: int, phone_number: str, usage_count: int):
        self.id = id
        self.phone_number = phone_number
        self.usage_count = usage_count

    def __str__(self):
        return f"User(id={self.id}, phone_number={self.phone_number}, usage_count={self.usage_count})"