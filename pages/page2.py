"""Record and manage income and expense transactions."""
import storage

TITLE = "เพิ่มรายการ"

CATEGORIES = [
    "เงินเดือน", "เงินค่าขนม", "รายได้เสริม", "อาหาร", "เดินทาง",
    "ที่พักและบิล", "การศึกษา", "สุขภาพ", "บันเทิง", "ช้อปปิ้ง", "อื่นๆ",
]


def build():
    all_items = storage.load()
    items = []
    position = 0

    for item in all_items:
        if item.get("type") in ("income", "expense"):
            item["no"] = position
            if "category" not in item:
                item["category"] = "ไม่ระบุหมวด"
            items.append(item)
        position = position + 1

    return {"items": items, "count": len(items), "categories": CATEGORIES}


def read_amount(text):
    try:
        amount = float(text)
    except ValueError:
        return None
    if amount <= 0 or amount != amount or amount in (float("inf"), float("-inf")):
        return None
    return amount


def handle(form):
    all_items = storage.load()

    if "delete" in form:
        position = form.get("delete", "")
        if position.isdigit() and int(position) < len(all_items):
            index = int(position)
            if all_items[index].get("type") in ("income", "expense"):
                removed = all_items.pop(index)
                storage.save(all_items)
                return "ลบรายการ " + removed["detail"] + " แล้ว"
        return "ไม่พบรายการที่ต้องการลบ"

    kind = form.get("type", "")
    category = form.get("category", "").strip()
    detail = form.get("detail", "").strip()
    amount = read_amount(form.get("amount", ""))

    if kind not in ("income", "expense"):
        return "กรุณาเลือกประเภทรายการ"
    if category not in CATEGORIES:
        return "กรุณาเลือกหมวดหมู่"
    if detail == "":
        return "กรุณากรอกรายละเอียด"
    if amount is None:
        return "จำนวนเงินต้องเป็นตัวเลขที่มากกว่า 0"

    all_items.append({
        "type": kind,
        "category": category,
        "detail": detail,
        "amount": amount,
    })
    storage.save(all_items)
    return "เพิ่มรายการ " + detail + " แล้ว"
