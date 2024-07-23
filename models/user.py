class User:
    def __init__(self, id, phone_number, usage_count, free_uses_left, purchased_uses):
        self.id = id
        self.phone_number = phone_number
        self.usage_count = usage_count
        self.free_uses_left = free_uses_left
        self.purchased_uses = purchased_uses