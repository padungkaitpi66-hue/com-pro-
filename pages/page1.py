"""Summarize income and expenses in a dashboard."""
import models
import storage

TITLE = "ภาพรวมการเงิน"


def build():
    all_items = storage.load()
    items = []
    total_income = 0
    total_expense = 0
    balance = 0
    position = 0

    for item in all_items:
        if item.get("type") in ("income", "expense"):
            item["no"] = position
            if "category" not in item:
                item["category"] = "ไม่ระบุหมวด"
            items.append(item)
            transaction = models.Transaction(
                item["type"], item["category"], item["detail"], item["amount"]
            )
            balance = balance + transaction.balance_change()
            if item["type"] == "income":
                total_income = total_income + item["amount"]
            else:
                total_expense = total_expense + item["amount"]
        position = position + 1

    return {
        "items": items,
        "count": len(items),
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": balance,
    }
