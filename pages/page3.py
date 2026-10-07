"""Analyze spending and suggest practical budget adjustments."""
import storage

TITLE = "วิเคราะห์การใช้เงิน"


def build():
    total_income = 0
    total_expense = 0
    category_totals = {}

    for item in storage.load():
        if item.get("type") == "income":
            total_income = total_income + item["amount"]
        elif item.get("type") == "expense":
            total_expense = total_expense + item["amount"]
            category = item.get("category", "ไม่ระบุหมวด")
            if category in category_totals:
                category_totals[category] = category_totals[category] + item["amount"]
            else:
                category_totals[category] = item["amount"]

    expense_rate = 0
    if total_income > 0:
        expense_rate = total_expense * 100 / total_income

    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": total_income - total_expense,
        "expense_rate": expense_rate,
        "bars": make_bars(category_totals, total_expense),
        "advice": make_advice(total_income, total_expense, category_totals, expense_rate),
    }


def make_bars(category_totals, total_expense):
    bars = []
    for category in category_totals:
        percent = 0
        if total_expense > 0:
            percent = int(category_totals[category] * 100 / total_expense)
        bars.append({"label": category, "amount": category_totals[category], "percent": percent})
    return bars


def make_advice(total_income, total_expense, category_totals, expense_rate):
    if total_expense == 0:
        return "ยังไม่มีรายการรายจ่าย เพิ่มข้อมูลในหน้าเพิ่มรายการเพื่อเริ่มวิเคราะห์"
    if total_income == 0:
        return "ยังไม่มีรายรับที่บันทึกไว้ ลองบันทึกรายรับเพื่อเปรียบเทียบกับรายจ่าย"

    biggest_category = ""
    biggest_amount = 0
    for category in category_totals:
        if category_totals[category] > biggest_amount:
            biggest_category = category
            biggest_amount = category_totals[category]

    if total_expense > total_income:
        gap = total_expense - total_income
        return "รายจ่ายมากกว่ารายรับ " + "{:,.2f}".format(gap) + " บาท ลองลดงบหมวด " + biggest_category
    if expense_rate >= 80:
        return "ใช้รายรับไปกับรายจ่าย " + "{:.1f}".format(expense_rate) + "% ลองตั้งงบรายสัปดาห์และลดหมวด " + biggest_category
    if biggest_amount * 100 / total_expense >= 40:
        share = biggest_amount * 100 / total_expense
        return "หมวด " + biggest_category + " เป็น " + "{:.1f}".format(share) + "% ของรายจ่าย ลองกำหนดงบหมวดนี้ให้ชัดเจน"
    return "รายจ่ายยังอยู่ในระดับที่รับมือได้ ลองบันทึกต่อเนื่องและกันเงินออมก่อนใช้จ่าย"
