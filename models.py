"""The transaction model used by the finance pages."""


class Transaction:
    def __init__(self, type, category, detail, amount):
        self.type = type
        self.category = category
        self.detail = detail
        self.amount = amount

    def balance_change(self):
        if self.type == "income":
            return self.amount
        return -self.amount
