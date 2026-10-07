# Website Source Bundle

Generated from the current project files. This is a reference bundle, not a standalone runnable website. Binary image assets are kept as separate files.

## app.py

```python

"""app.py — GIVEN, DO NOT EDIT.

Turns every file in pages/ into a web page:

    pages/page1.py  →  http://localhost:5000/page1   rendered with templates/page1.html

A page file needs:
    TITLE = "..."                # shown in the menu
    def build():                 # runs on every visit, returns a dict for the template
    def build(query):            # same, but receives the ?a=b URL parameters as a dict
    def handle(form):            # optional, runs when the page's <form method="post"> is sent

Extras the web layer does for you (see docs/tools/flask-page.md):
  - a string returned by handle() becomes the yellow banner on the next page load
  - a "notice" key in build()'s dict is shown as the banner too
  - an uploaded file (<input type="file" name="photo">, form with enctype="multipart/form-data")
    is saved into static/img/ and form["photo"] becomes the saved file name
    (if handle() does not store that name in data.json, the file is removed again)
  - after a POST you are sent back to the same URL you came from (filters survive)
  - a page that is missing, broken, or still a TODO shows a friendly "not built yet" page
Run:  python app.py           (or  python app.py 5001  to pick another port)
"""
import importlib.util
import inspect
import json
import os
import re
import sys
import time
import traceback
from urllib.parse import urlsplit

from flask import Flask, redirect, render_template, request, url_for

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES_DIR = os.path.join(HERE, "pages")
UPLOAD_DIR = os.path.join(HERE, "static", "img")
ALLOWED_UPLOAD = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
sys.path.insert(0, HERE)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024      # 5 MB per upload


# ---------- helpers ----------
def read_json(name, default):
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def page_names():
    """page1, page2, ... in order, then everything else, team last."""
    names = [f[:-3] for f in os.listdir(PAGES_DIR) if f.endswith(".py") and not f.startswith("_")]
    numbered = sorted([n for n in names if n.startswith("page") and n[4:].isdigit()], key=lambda n: int(n[4:]))
    others = sorted(n for n in names if n not in numbered and n != "team")
    tail = ["team"] if "team" in names else []
    return numbered + others + tail


def load_page(name):
    """Import pages/<name>.py fresh every time, so edits show up on reload.
    (This also means a variable at the top of a page file does NOT survive between visits —
    keep anything that must persist in data.json.)  Returns (module, error_text)."""
    path = os.path.join(PAGES_DIR, name + ".py")
    if not os.path.exists(path):
        return None, "ไม่พบไฟล์ pages/" + name + ".py"
    try:
        spec = importlib.util.spec_from_file_location("pages." + name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, None
    except Exception:
        return None, traceback.format_exc()


def nav():
    items = []
    for name in page_names():
        module, _ = load_page(name)
        title = getattr(module, "TITLE", None) if module else None
        items.append({"name": name, "title": title or name.capitalize()})
    return items


def save_uploads(files):
    """Save every uploaded file into static/img/ and return {field: saved_name}."""
    saved = {}
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    for field in files:
        f = files[field]
        if not f or not f.filename:
            continue
        base, ext = os.path.splitext(f.filename)
        ext = ext.lower()
        if ext not in ALLOWED_UPLOAD:
            saved[field] = ""          # wrong type → empty string, the page can complain
            continue
        clean = re.sub(r"[^A-Za-z0-9_-]+", "-", base).strip("-")[:40] or "file"
        name = clean + "-" + str(int(time.time())) + ext
        f.save(os.path.join(UPLOAD_DIR, name))
        saved[field] = name
    return saved


def drop_unused_uploads(uploaded):
    """An uploaded file that handle() did not store in data.json (rejected form) is removed again."""
    names = [n for n in uploaded.values() if n]
    if not names:
        return
    try:
        with open(os.path.join(HERE, "data.json"), encoding="utf-8") as f:
            stored = f.read()
    except OSError:
        stored = ""
    for n in names:
        if n not in stored:
            try:
                os.remove(os.path.join(UPLOAD_DIR, n))
            except OSError:
                pass


def back_to(name, msg=None):
    """Redirect to the page the form came from (keeps ?q=… filters), else to /<name>."""
    target = url_for("page", name=name)
    ref = request.referrer
    if ref:
        parts = urlsplit(ref)
        if parts.path == target:
            target = parts.path + ("?" + parts.query if parts.query else "")
    if msg:
        joiner = "&" if "?" in target else "?"
        target = target + joiner + "msg=" + msg
    return redirect(target)


@app.context_processor
def inject_globals():
    return {
        "nav": nav(),
        "team": read_json("team.json", {"group": {}, "members": []}),
        "msg": request.args.get("msg", ""),
    }


def not_built(name, reason, detail=""):
    return render_template("_not_built.html", page=name, reason=reason, detail=detail), 200


# ---------- routes ----------
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/<name>", methods=["GET", "POST"])
def page(name):
    if name not in page_names():
        return not_built(name, "ไม่มีหน้านี้")

    module, error = load_page(name)
    if error:
        return not_built(name, "ไฟล์ pages/" + name + ".py มีข้อผิดพลาด", error)

    # POST → handle(form) → redirect back (with an optional message)
    if request.method == "POST":
        handler = getattr(module, "handle", None)
        if handler is None:
            return not_built(name, "หน้านี้รับฟอร์มไม่ได้: ยังไม่มี def handle(form) ใน pages/" + name + ".py")
        form = dict(request.form)
        uploaded = save_uploads(request.files)
        form.update(uploaded)
        try:
            result = handler(form)
        except NotImplementedError:
            return not_built(name, "handle() ยังเป็น TODO")
        except Exception:
            return not_built(name, "handle() พัง", traceback.format_exc())
        finally:
            drop_unused_uploads(uploaded)
        if isinstance(result, str) and result:
            return back_to(name, result)
        return back_to(name)

    # GET → build() → template
    builder = getattr(module, "build", None)
    if builder is None:
        return not_built(name, "ยังไม่มี def build() ใน pages/" + name + ".py")
    try:
        if len(inspect.signature(builder).parameters) >= 1:
            query = dict(request.args)
            query.pop("msg", None)
            context = builder(query)
        else:
            context = builder()
    except NotImplementedError:
        return not_built(name, "build() ยังเป็น TODO")
    except Exception:
        return not_built(name, "build() พัง", traceback.format_exc())

    if context is None:
        context = {}
    if not isinstance(context, dict):
        return not_built(name, "build() ต้อง return dict แต่ได้ " + type(context).__name__)

    template = name + ".html"
    if not os.path.exists(os.path.join(HERE, "templates", template)):
        return not_built(name, "ไม่พบไฟล์ templates/" + template)
    try:
        return render_template(template, title=getattr(module, "TITLE", name), page=name, **context)
    except Exception:
        return not_built(name, "templates/" + template + " มีข้อผิดพลาด", traceback.format_exc())


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    app.run(debug=True, port=port)

```

## storage.py

```python

"""storage.py — GIVEN, DO NOT EDIT.

Your data lives in data.json as a list of dicts. Two functions:

    items = storage.load()      # read the list  (empty list if the file is missing)
    storage.save(items)         # write the list back, nicely formatted

Open data.json in VS Code to see or edit the data by hand.
Broke it while testing?  storage.reset()  copies data.sample.json back over data.json
(or just copy the file yourself).
"""
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, "data.json")
SAMPLE_FILE = os.path.join(HERE, "data.sample.json")


def load():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def save(items):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def reset():
    """Put data.json back to data.sample.json (your own starting data — keep it updated)."""
    if os.path.exists(SAMPLE_FILE):
        shutil.copyfile(SAMPLE_FILE, DATA_FILE)
        return True
    return False

```

## models.py

```python

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

```

## portable_launcher.py

```python

"""Start the packaged finance app without requiring Python on the target PC."""
import os
import shutil
import sys
import webbrowser
from pathlib import Path

import storage
from app import app
from werkzeug.serving import make_server


def resource_directory():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def prepare_user_data():
    app_data = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "TheLastHope"
    app_data.mkdir(parents=True, exist_ok=True)

    data_file = app_data / "data.json"
    if not data_file.exists():
        shutil.copyfile(resource_directory() / "data.json", data_file)

    storage.DATA_FILE = str(data_file)
    storage.SAMPLE_FILE = str(resource_directory() / "data.sample.json")


def start_server():
    port = 5000
    while port <= 5010:
        try:
            return make_server("127.0.0.1", port, app, threaded=True)
        except OSError:
            port = port + 1
    raise RuntimeError("ไม่พบพอร์ตว่างระหว่าง 5000 ถึง 5010")


def main():
    prepare_user_data()
    server = start_server()
    url = "http://127.0.0.1:" + str(server.server_port) + "/page1"
    print("The Last Hope is running at " + url)
    print("ปิดหน้าต่างนี้เพื่อหยุดเว็บไซต์")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

```

## check_project.py

```python

"""check_project.py — GIVEN, DO NOT EDIT.   Run anytime:  python check_project.py

Prints the automated part of your grade (60 of 100):
  pages running      30   page1, page2, page3 each load without error and their source has no TODO left
  Python foundations 30   if/else 7 · loop 7 · function 7 · class 9   found in pages/page*.py + models.py
The other 40 (teamwork + presentation) is given by your teacher.

Also prints WARNINGS that cost no points here but that your teacher will look at:
  - a page whose Python has no loop and no if (may not count as one of pages 1–3)
  - a handle(form) that crashes on an empty form
  - a given file that was edited
"""
import ast
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REQUIRED_PAGES = ["page1", "page2", "page3"]
GIVEN_FILES = ["app.py", "storage.py", "check_project.py", "test_pages.py",
               "templates/base.html", "templates/_not_built.html"]
HASH_FILE = os.path.join(HERE, ".given_hashes.json")
NOT_BUILT_MARK = "ยังไม่พร้อม"
POINTS = {"if": 7, "loop": 7, "function": 7, "class": 9}


def sha(rel):
    with open(os.path.join(HERE, *rel.split("/")), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def mark(ok):
    return "✓" if ok else "✗"


def read(rel):
    with open(os.path.join(HERE, *rel.split("/")), encoding="utf-8") as f:
        return f.read()


def student_python_files():
    files = ["models.py"]
    for name in sorted(os.listdir(os.path.join(HERE, "pages"))):
        if name.startswith("page") and name.endswith(".py"):
            files.append("pages/" + name)
    return files


def source_has_todo(name):
    """TODO left in the page's own source files (not in data, not in rendered output)."""
    for rel in ["pages/" + name + ".py", "templates/" + name + ".html"]:
        p = os.path.join(HERE, *rel.split("/"))
        if os.path.exists(p) and "TODO" in read(rel):
            return True
    return False


def page_constructs(name):
    """(has_loop_or_if, has_handle, handle_crash_text) for pages/<name>.py"""
    rel = "pages/" + name + ".py"
    p = os.path.join(HERE, *rel.split("/"))
    if not os.path.exists(p):
        return False, False, ""
    try:
        tree = ast.parse(read(rel))
    except Exception:
        return False, False, ""
    logic = any(isinstance(n, (ast.If, ast.For, ast.While)) for n in ast.walk(tree))
    has_handle = any(isinstance(n, ast.FunctionDef) and n.name == "handle" for n in ast.walk(tree))
    crash = ""
    if has_handle:
        import app as webapp
        module, err = webapp.load_page(name)
        if module is not None:
            try:
                module.handle({})
            except NotImplementedError:
                crash = "handle() is still a TODO"
            except Exception as e:
                crash = type(e).__name__ + ": " + str(e)[:60]
            finally:
                # handle({}) may have written data — put the sample back if one exists
                try:
                    import storage
                    storage.reset()
                except Exception:
                    pass
    return logic, has_handle, crash


# ---------- pages running ----------
def check_pages():
    import app as webapp
    client = webapp.app.test_client()
    rows, warnings = [], []
    total = 0
    all_pages = webapp.page_names()
    for name in REQUIRED_PAGES + [p for p in all_pages if p not in REQUIRED_PAGES and p != "team"]:
        required = name in REQUIRED_PAGES
        try:
            r = client.get("/" + name)
            html = r.get_data(as_text=True)
            status = r.status_code
        except Exception as e:
            html, status = "", "crash: " + type(e).__name__
        loads = status == 200 and NOT_BUILT_MARK not in html
        todo = source_has_todo(name)
        note = ""
        if status != 200:
            note = "HTTP " + str(status)
        elif NOT_BUILT_MARK in html:
            start = html.find('class="reason">')
            note = html[start + 15: html.find("<", start + 15)].strip() if start > 0 else "not built"
        elif todo:
            note = "TODO still in pages/" + name + ".py or templates/" + name + ".html"
        ok = loads and not todo
        pts = 10 if ok else 0
        if required:
            total += pts
            rows.append((name, mark(ok), note, f"{pts}/10"))
        else:
            rows.append((name, mark(ok), note or "extra page", "bonus"))
        if loads:
            logic, has_handle, crash = page_constructs(name)
            if not logic:
                warnings.append(f"/{name}: no loop and no if in pages/{name}.py — a page with no Python work may not count as one of pages 1–3")
            if crash:
                warnings.append(f"/{name}: handle() crashes on an empty form ({crash}) — use form.get(...) and check values")
    return rows, total, warnings


# ---------- foundations ----------
def check_foundations():
    found = {"if": [], "loop": [], "function": [], "class": []}
    class_details = []
    import_errors = []
    for rel in student_python_files():
        try:
            src = read(rel)
            tree = ast.parse(src)
        except Exception as e:
            import_errors.append(f"{rel}: {type(e).__name__}: {e}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                found["if"].append(rel)
            elif isinstance(node, (ast.For, ast.While)):
                found["loop"].append(rel)
            elif isinstance(node, ast.FunctionDef) and node.name != "__init__":
                found["function"].append(rel + ":" + node.name)
            elif isinstance(node, ast.ClassDef):
                methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                if "__init__" in methods and len(methods) >= 2:
                    still_todo = "TODO" in ast.get_source_segment(src, node)
                    class_details.append((rel, node.name, len(methods) - 1, still_todo))
                    if not still_todo:
                        found["class"].append(rel + ":" + node.name)

    def uniq(xs):
        out = []
        for x in xs:
            if x not in out:
                out.append(x)
        return out

    rows = []
    total = 0
    labels = {"if": "if / else", "loop": "loop (for / while)", "function": "function (def)", "class": "class + method"}
    for key in ["if", "loop", "function", "class"]:
        where = uniq(found[key])
        ok = len(where) > 0
        pts = POINTS[key] if ok else 0
        total += pts
        if key == "class" and not ok and class_details:
            rel, name, _, _ = class_details[0]
            note = f"{rel} {name} still has a TODO — finish it"
        elif key == "class" and ok:
            note = ", ".join(where)
        elif key == "function":
            note = f"{len(where)} found" if ok else "no def found"
        else:
            note = ", ".join(where[:3]) + (" …" if len(where) > 3 else "") if ok else "none found"
        rows.append((labels[key], mark(ok), note, f"{pts}/{POINTS[key]}"))
    return rows, total, import_errors


# ---------- given files ----------
def check_given():
    if not os.path.exists(HASH_FILE):
        return None, [], []
    expected = json.load(open(HASH_FILE))
    changed, checked = [], []
    for rel, h in expected.items():
        rel = rel.replace("\\", "/")
        p = os.path.join(HERE, *rel.split("/"))
        if not os.path.exists(p):
            changed.append(rel + " (missing)")
        elif sha(rel) != h:
            changed.append(rel)
        else:
            checked.append(rel.split("/")[-1])
    return True, changed, checked


def main():
    group = "?"
    try:
        group = json.load(open(os.path.join(HERE, "team.json"), encoding="utf-8"))["group"]["name"]
    except Exception:
        pass

    print(f"check_project · {group}")
    page_rows, page_total, warnings = check_pages()
    print("  pages running")
    for name, m, note, pts in page_rows:
        print(f"    /{name:<8} {m}  {note:<52} {pts:>6}")
    print(f"    {'':<9}    {'':<52} {page_total:>3}/30")

    f_rows, f_total, errors = check_foundations()
    print("  Python foundations (pages/page*.py + models.py)")
    for label, m, note, pts in f_rows:
        print(f"    {label:<20} {m}  {note:<40} {pts:>6}")
    for e in errors:
        print(f"    ! cannot read: {e}")
    print(f"    {'':<20}    {'':<40} {f_total:>3}/30")

    has_hashes, changed, checked = check_given()
    if has_hashes is None:
        print("  given files ............ (no .given_hashes.json — skipped)")
    else:
        shown = ", ".join(changed) if changed else ", ".join(checked)
        print(f"  given files unchanged .. {mark(not changed)}  {shown}")
        if changed:
            warnings.append("given files were edited: " + ", ".join(changed) + " — restore them from the original skeleton")

    score = page_total + f_total
    print("  " + "-" * 64)
    print(f"  automated score: {score} / 60   (+ teamwork & presentation 40, from your teacher)")
    if warnings:
        print("  warnings (no points lost here, but your teacher will see them)")
        for w in warnings:
            print(f"    ! {w}")
    return 0 if score == 60 else 1


if __name__ == "__main__":
    if "--write-hashes" in sys.argv:
        json.dump({rel: sha(rel) for rel in GIVEN_FILES if os.path.exists(os.path.join(HERE, *rel.split("/")))},
                  open(HASH_FILE, "w"), indent=1)
        print("hashes written to .given_hashes.json")
        sys.exit(0)
    sys.exit(main())

```

## test_pages.py

```python

"""test_pages.py — GIVEN, DO NOT EDIT.   Run:  pytest

Four tests: page1, page2, page3 each load (not a "not built yet" page, no TODO left in
their source), and team.json has been filled in.
This is the "pages running" part of check_project.py, in pytest form.
"""
import os

import pytest

import app as webapp

HERE = os.path.dirname(os.path.abspath(__file__))
NOT_BUILT_MARK = "ยังไม่พร้อม"


@pytest.fixture
def client():
    return webapp.app.test_client()


def _source(rel):
    with open(os.path.join(HERE, *rel.split("/")), encoding="utf-8") as f:
        return f.read()


@pytest.mark.parametrize("name", ["page1", "page2", "page3"])
def test_page_loads(client, name):
    r = client.get("/" + name)
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert NOT_BUILT_MARK not in html, f"/{name} is not built yet — see PAGES.md"
    assert "TODO" not in _source("pages/" + name + ".py"), f"pages/{name}.py still has a TODO"
    assert "TODO" not in _source("templates/" + name + ".html"), f"templates/{name}.html still has a TODO"


def test_team_page_filled(client):
    html = client.get("/team").get_data(as_text=True)
    assert "66xxxxxxx" not in html, "team.json still has the placeholder student ids"

```

## data.json

```json

[]

```

## data.sample.json

```json

[
  {"type": "income", "category": "เงินเดือน", "detail": "รายรับประจำ", "amount": 18000},
  {"type": "expense", "category": "อาหาร", "detail": "ค่าอาหาร", "amount": 4200},
  {"type": "expense", "category": "เดินทาง", "detail": "ค่าเดินทาง", "amount": 1200},
  {"type": "expense", "category": "บันเทิง", "detail": "สันทนาการ", "amount": 900},
  {"type": "expense", "category": "ช้อปปิ้ง", "detail": "ของใช้ส่วนตัว", "amount": 1700}
]

```

## team.json

```json

{
  "group": {
    "name": "The last hope",
    "section": "sec 6",
    "topic": "ระบบบันทึกรายรับและรายจ่าย",
    "description": "บันทึกรายการ สรุปเงินคงเหลือ และวิเคราะห์การใช้จ่ายเพื่อช่วยวางแผนการเงิน"
  },
  "members": [
    {"name": "นายวรวุฒิ สมสี", "id": "65130045220", "role": "Data Engineer", "task": "data.json · models.py · page1 Dashboard: สรุปรายการแบบ List และตกแต่งเว็บไซต์"},
    {"name": "นายผดุงเกียรติ พิมโคตร", "id": "66130043531", "role": "QA / Test", "task": "check.bat · ออกแบบ data.json · class ใน models.py · page2 Form"},
    {"name": "นายภานุเทพ ชัยบุตร", "id": "66130044134", "role": "Project Lead (PM)", "task": "ออกแบบ data.json · class ใน models.py · page2 Form"},
    {"name": "นายศักรินทร์ ปัญญาพ่อ", "id": "66130046583", "role": "Frontend Dev (HTML/CSS)", "task": "ออกแบบ data.json · class ใน models.py · page2 Form"}
  ]
}

```

## requirements.txt

```text

flask
pytest

```

## requirements-build.txt

```text

pyinstaller>=6.0,<7.0

```

## run.bat

```bat

@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo Run setup.bat first. & pause & exit /b 1)
set PYTHONIOENCODING=utf-8
set PORT=%1
if "%PORT%"=="" set PORT=5000
echo Starting on http://localhost:%PORT%   (Ctrl+C to stop)
start "" http://localhost:%PORT%
".venv\Scripts\python.exe" app.py %PORT%

```

## setup.bat

```bat

@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo === Computer Programming Project : setup ===
where python >nul 2>nul || (echo [!] python not found. Install Python 3.12+ from python.org and tick "Add python.exe to PATH". & pause & exit /b 1)
python -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" || (echo [!] Python 3.11 or newer is required. & python --version & pause & exit /b 1)
if not exist .venv (
  echo [1/2] creating .venv ...
  python -m venv .venv || (echo [!] could not create .venv & pause & exit /b 1)
) else (
  echo [1/2] .venv already exists
)
echo [2/2] installing flask + pytest ...
".venv\Scripts\python.exe" -m pip install --quiet --no-index --find-links wheels -r requirements.txt 2>nul
if errorlevel 1 (
  echo     offline wheels did not match this Python - trying online ...
  ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt || (echo [!] install failed - check your internet connection & pause & exit /b 1)
)
".venv\Scripts\python.exe" -c "import flask, pytest; print('    flask', flask.__version__ if hasattr(flask,'__version__') else 'ok', '/ pytest', pytest.__version__)"
echo.
echo Done. Next:  run.bat   (opens the site)    check.bat   (score + tests)
pause

```

## check.bat

```bat

@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo Run setup.bat first. & pause & exit /b 1)
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" check_project.py
echo.
echo --- pytest ---
".venv\Scripts\python.exe" -m pytest -q
pause

```

## run.sh

```bash

#!/usr/bin/env bash
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { echo "Run  bash setup.sh  first."; exit 1; }
export PYTHONIOENCODING=utf-8
PORT=${1:-5000}
echo "Starting on http://localhost:$PORT   (Ctrl+C to stop)"
(command -v open >/dev/null && open "http://localhost:$PORT") || (command -v xdg-open >/dev/null && xdg-open "http://localhost:$PORT") || true
.venv/bin/python app.py "$PORT"

```

## setup.sh

```bash

#!/usr/bin/env bash
# Computer Programming Project : setup (macOS / Linux)     usage:  bash setup.sh
cd "$(dirname "$0")"
PY=python3; command -v python3 >/dev/null 2>&1 || PY=python
command -v $PY >/dev/null 2>&1 || { echo "[!] python not found. Install Python 3.12+"; exit 1; }
$PY -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' || { echo "[!] Python 3.11 or newer is required"; $PY --version; exit 1; }
if [ ! -d .venv ]; then echo "[1/2] creating .venv ..."; $PY -m venv .venv || exit 1; else echo "[1/2] .venv already exists"; fi
echo "[2/2] installing flask + pytest ..."
if ! .venv/bin/python -m pip install --quiet --no-index --find-links wheels -r requirements.txt 2>/dev/null; then
  echo "    offline wheels did not match this Python - trying online ..."
  .venv/bin/python -m pip install --quiet -r requirements.txt || { echo "[!] install failed"; exit 1; }
fi
.venv/bin/python -c "import flask, pytest; print('    flask ok / pytest', pytest.__version__)"
echo; echo "Done. Next:  bash run.sh   (opens the site)    bash check.sh   (score + tests)"

```

## check.sh

```bash

#!/usr/bin/env bash
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { echo "Run  bash setup.sh  first."; exit 1; }
export PYTHONIOENCODING=utf-8
.venv/bin/python check_project.py
echo; echo "--- pytest ---"
.venv/bin/python -m pytest -q

```

## build_windows.bat

```bat

@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo Run setup.bat first. & pause & exit /b 1)

".venv\Scripts\python.exe" -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
  echo Installing the Windows packaging tool...
  ".venv\Scripts\python.exe" -m pip install -r requirements-build.txt || (echo [!] Could not install PyInstaller. Check your internet connection. & pause & exit /b 1)
)

echo Building the standalone Windows app...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --console --name TheLastHope --distpath dist --workpath build --specpath build --add-data "%CD%\pages;pages" --add-data "%CD%\templates;templates" --add-data "%CD%\static;static" --add-data "%CD%\team.json;." --add-data "%CD%\data.json;." --add-data "%CD%\data.sample.json;." --hidden-import models portable_launcher.py
if errorlevel 1 (echo [!] Build failed. & pause & exit /b 1)

echo.
echo Done: dist\TheLastHope.exe
echo Upload this single EXE to GitHub Releases. The target PC does not need Python.
pause

```

## pages\page1.py

```python

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

```

## pages\page2.py

```python

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

```

## pages\page3.py

```python

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

```

## pages\team.py

```python

"""pages/team.py — the team page. Already works: it shows team.json.

Week 0 task: open team.json, put in your group name, topic, and every member's
name / student id / role / task. Then look at /team. You may also change this file
and templates/team.html to make the page your own.
"""
import json
import os

TITLE = "ทีม"

TITLES = ["นางสาว", "นาย", "นาง", "ว่าที่ร้อยตรี", "Mr.", "Ms.", "Miss"]


def initial_of(name):
    """First letter of the given name, skipping Thai/English titles."""
    name = name.strip()
    for t in TITLES:
        if name.startswith(t):
            name = name[len(t):].strip()
    if name == "":
        return "?"
    return name[0]


def build():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "team.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    members = []
    for m in data["members"]:
        m["initial"] = initial_of(m["name"])
        members.append(m)
    return {"group": data["group"], "members": members, "count": len(members)}

```

## templates\base.html

```html

<!doctype html>
{# base.html — GIVEN, DO NOT EDIT. Header, menu and footer for every page.
   Your page goes inside {% block content %} in your own templates/pageN.html.
   Page-specific JavaScript goes inside {% block scripts %} (or static/js/pageN.js). #}
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title or team.group.name }} · {{ team.group.name }}</title>
<link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
{% block head %}{% endblock %}
</head>
<body>
<header class="site-header">
  <div class="wrap header-row">
    <a class="brand" href="{{ url_for('home') }}">
      <img src="{{ url_for('static', filename='eng-logo.png') }}" alt="คณะวิศวกรรมศาสตร์ ม.อุบลฯ">
      <span class="brand-text">
        <span class="brand-line1">คณะวิศวกรรมศาสตร์ มหาวิทยาลัยอุบลราชธานี</span>
        <span class="brand-line2">1309102 การเขียนโปรแกรมคอมพิวเตอร์ · Computer Programming Project</span>
      </span>
    </a>
    <span class="group-badge">{{ team.group.name }} · {{ team.group.section }}</span>
  </div>
  <nav class="wrap site-nav">
    <a href="{{ url_for('home') }}" class="{{ 'active' if request.path == '/' }}">หน้าแรก</a>
    {% for p in nav %}
      <a href="{{ url_for('page', name=p.name) }}" class="{{ 'active' if request.path == '/' + p.name }}">{{ p.title }}</a>
    {% endfor %}
  </nav>
</header>

<main class="wrap">
  {% if msg %}<div class="banner">{{ msg }}</div>{% endif %}
  {% if notice %}<div class="banner">{{ notice }}</div>{% endif %}
  {% block content %}{% endblock %}
</main>

<footer class="site-footer">
  <div class="wrap">
    <span>{{ team.group.name }} — {{ team.group.topic }}</span>
    <span class="members">
      {% for m in team.members %}{{ m.name }}{% if not loop.last %} · {% endif %}{% endfor %}
    </span>
  </div>
</footer>
{% block scripts %}{% endblock %}
</body>
</html>

```

## templates\home.html

```html

{% extends "base.html" %}
{# home.html — the front page. You may edit this freely. #}
{% block content %}
<section class="hero">
  <h1>{{ team.group.topic }}</h1>
  <p class="lead">{{ team.group.description }}</p>
</section>

<section class="cards">
  {% for p in nav %}
  <a class="card" href="{{ url_for('page', name=p.name) }}">
    <span class="card-kicker">{{ p.name }}</span>
    <span class="card-title">{{ p.title }}</span>
  </a>
  {% endfor %}
</section>
{% endblock %}

```

## templates\page1.html

```html

{% extends "base.html" %}
{% block content %}
<h1>{{ title }}</h1>
<p class="lead">สรุปยอดเงินและรายการรายรับรายจ่ายทั้งหมด {{ count }} รายการ</p>

<div class="stat-grid">
	<div class="stat good">
		<span class="label">รายรับรวม</span>
		<strong class="value">{{ "{:,.2f}".format(total_income) }} บาท</strong>
	</div>
	<div class="stat bad">
		<span class="label">รายจ่ายรวม</span>
		<strong class="value">{{ "{:,.2f}".format(total_expense) }} บาท</strong>
	</div>
	<div class="stat">
		<span class="label">เงินคงเหลือ</span>
		<strong class="value">{{ "{:,.2f}".format(balance) }} บาท</strong>
	</div>
</div>

<section class="panel">
	<h2 style="margin-top:0">รายการล่าสุด</h2>
	{% if items %}
	<table>
		<tr><th>รายการ</th><th>หมวดหมู่</th><th class="num">จำนวนเงิน</th></tr>
		{% for item in items|reverse %}
		<tr>
			<td>
				{% if item.type == "income" %}
				<span class="badge">รายรับ</span>
				{% else %}
				<span class="badge">รายจ่าย</span>
				{% endif %}
				{{ item.detail }}
			</td>
			<td>{{ item.category }}</td>
			<td class="num">{{ "{:,.2f}".format(item.amount) }} บาท</td>
		</tr>
		{% endfor %}
	</table>
	{% else %}
	<div class="empty">ยังไม่มีรายการ ไปที่หน้าเพิ่มรายการเพื่อเริ่มบันทึก</div>
	{% endif %}
</section>
{% endblock %}

```

## templates\page2.html

```html

{% extends "base.html" %}
{% block content %}
<h1>{{ title }}</h1>
<p class="lead">บันทึกรายรับและรายจ่ายทั้งหมด {{ count }} รายการ</p>

<div class="two-col">
	<form method="post" class="panel">
		<h2 style="margin-top:0">เพิ่มรายการใหม่</h2>
		<div class="field">
			<label for="type">ประเภทรายการ</label>
			<select id="type" name="type" required>
				<option value="income">รายรับ</option>
				<option value="expense">รายจ่าย</option>
			</select>
		</div>
		<div class="field">
			<label for="category">หมวดหมู่</label>
			<select id="category" name="category" required>
				{% for category in categories %}
				<option value="{{ category }}">{{ category }}</option>
				{% endfor %}
			</select>
		</div>
		<div class="field">
			<label for="detail">รายละเอียด</label>
			<input id="detail" name="detail" placeholder="เช่น ค่าอาหารกลางวัน" required>
		</div>
		<div class="field">
			<label for="amount">จำนวนเงิน (บาท)</label>
			<input id="amount" name="amount" type="number" min="0.01" step="0.01" placeholder="0.00" required>
		</div>
		<button class="btn" type="submit">บันทึกรายการ</button>
	</form>

	<section class="panel">
		<h2 style="margin-top:0">รายการที่บันทึก</h2>
		{% if items %}
		<table>
			<tr><th>รายการ</th><th>หมวด</th><th class="num">จำนวนเงิน</th><th></th></tr>
			{% for item in items|reverse %}
			<tr>
				<td>
					{% if item.type == "income" %}
					<span class="badge">รายรับ</span>
					{% else %}
					<span class="badge">รายจ่าย</span>
					{% endif %}
					{{ item.detail }}
				</td>
				<td>{{ item.category }}</td>
				<td class="num">{{ "{:,.2f}".format(item.amount) }} บาท</td>
				<td style="text-align:right">
					<form method="post" class="inline">
						<input type="hidden" name="delete" value="{{ item.no }}">
						<button class="btn small danger" type="submit">ลบ</button>
					</form>
				</td>
			</tr>
			{% endfor %}
		</table>
		{% else %}
		<div class="empty">ยังไม่มีรายการ ลองเพิ่มรายการแรกได้เลย</div>
		{% endif %}
	</section>
</div>
{% endblock %}

```

## templates\page3.html

```html

{% extends "base.html" %}
{% block content %}
<h1>{{ title }}</h1>
<p class="lead">คำแนะนำอัตโนมัติจากข้อมูลรายรับและรายจ่ายที่บันทึกไว้</p>

<div class="stat-grid">
	<div class="stat good">
		<span class="label">รายรับรวม</span>
		<strong class="value">{{ "{:,.2f}".format(total_income) }} บาท</strong>
	</div>
	<div class="stat bad">
		<span class="label">รายจ่ายรวม</span>
		<strong class="value">{{ "{:,.2f}".format(total_expense) }} บาท</strong>
	</div>
	<div class="stat">
		<span class="label">ใช้รายรับไปแล้ว</span>
		<strong class="value">{{ "{:.1f}".format(expense_rate) }}%</strong>
	</div>
	<div class="stat">
		<span class="label">เงินคงเหลือ</span>
		<strong class="value">{{ "{:,.2f}".format(balance) }} บาท</strong>
	</div>
</div>

<section class="panel" style="margin-bottom:18px">
	<h2 style="margin-top:0">คำแนะนำ</h2>
	<p>{{ advice }}</p>
	<p class="muted">เป็นการวิเคราะห์ตามกฎจากข้อมูลที่บันทึก ไม่ได้ส่งข้อมูลออกไปยังบริการ AI ภายนอก</p>
</section>

<section class="panel">
	<h2 style="margin-top:0">สัดส่วนรายจ่ายตามหมวด</h2>
	{% if bars %}
		{% for bar in bars %}
		<div class="bar-row">
			<span>{{ bar.label }}</span>
			<div class="bar-track"><div class="bar-fill" style="width: {{ bar.percent }}%"></div></div>
			<span class="num">{{ "{:,.2f}".format(bar.amount) }} บาท</span>
		</div>
		{% endfor %}
	{% else %}
	<div class="empty">ยังไม่มีข้อมูลรายจ่ายให้วิเคราะห์</div>
	{% endif %}
</section>
{% endblock %}

```

## templates\team.html

```html

{% extends "base.html" %}
{# templates/team.html — the team page. Basic layout given; fill team.json, then make it yours. #}
{% block content %}
<h1>{{ group.name }} <small class="muted">· {{ group.section }}</small></h1>
<p class="lead">{{ group.topic }} — {{ group.description }}</p>

<h2>สมาชิก ({{ count }} คน)</h2>
<div class="member-grid">
  {% for m in members %}
  <div class="member">
    <div class="avatar">{{ m.initial }}</div>
    <div class="member-name">{{ m.name }}</div>
    <div class="muted">{{ m.id }}</div>
    <div class="role">{{ m.role }}</div>
    <div class="task">{{ m.task }}</div>
  </div>
  {% endfor %}
</div>

<h2>ตารางงาน</h2>
<table>
  <tr><th>ชื่อ</th><th>รหัส</th><th>บทบาท</th><th>งานที่รับผิดชอบ</th></tr>
  {% for m in members %}
  <tr><td>{{ m.name }}</td><td>{{ m.id }}</td><td>{{ m.role }}</td><td>{{ m.task }}</td></tr>
  {% endfor %}
</table>
{% endblock %}

```

## templates\_not_built.html

```html

{% extends "base.html" %}
{# _not_built.html — GIVEN. Shown when a page is missing, still a TODO, or crashed. #}
{% block content %}
<div class="notbuilt">
  <h2>🚧 /{{ page }} — ยังไม่พร้อม</h2>
  <p class="reason">{{ reason }}</p>
  {% if detail %}
  <details open>
    <summary>รายละเอียดข้อผิดพลาด (คัดลอกไปถาม Copilot ได้: <code>/explain-error</code>)</summary>
    <pre>{{ detail }}</pre>
  </details>
  {% endif %}
  <p class="hint">
    ขั้นตอน: เปิด <code>PAGES.md</code> → เลือกแบบหน้าจาก <code>catalog/</code> →
    เขียน <code>pages/{{ page }}.py</code> + <code>templates/{{ page }}.html</code> →
    โหลดหน้านี้ใหม่ → <code>python check_project.py</code>
  </p>
</div>
{% endblock %}

```

## static\style.css

```css

/* style.css — given, but you may ADD your own rules at the bottom. */
:root {
  --maroon: #7a1f2b;
  --maroon-dark: #5c1620;
  --gold: #e6b422;
  --ink: #1f2933;
  --muted: #6b7280;
  --line: #e5e7eb;
  --bg: #f7f5f2;
  --card: #ffffff;
}
* { box-sizing: border-box; }
html, body { margin: 0; }
body {
  font-family: "Segoe UI", Sarabun, "Noto Sans Thai", system-ui, sans-serif;
  color: var(--ink);
  background: var(--bg);
  line-height: 1.55;
  display: flex; flex-direction: column; min-height: 100vh;
}
.wrap { max-width: 960px; margin: 0 auto; padding: 0 20px; width: 100%; }

/* ---------- header ---------- */
.site-header { background: linear-gradient(180deg, var(--maroon), var(--maroon-dark)); color: #fff; }
.header-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 12px 20px; }
.brand { display: flex; align-items: center; gap: 14px; color: #fff; text-decoration: none; }
.brand img { height: 56px; width: 56px; border-radius: 50%; background: #fff; padding: 2px; }
.brand-text { display: flex; flex-direction: column; }
.brand-line1 { font-weight: 700; font-size: 17px; letter-spacing: .2px; }
.brand-line2 { font-size: 12.5px; opacity: .85; }
.group-badge { font-size: 13px; background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.3); padding: 4px 12px; border-radius: 999px; white-space: nowrap; }
.site-nav { display: flex; gap: 4px; flex-wrap: wrap; padding: 0 20px 0; border-top: 1px solid rgba(255,255,255,.15); }
.site-nav a { color: #fff; text-decoration: none; padding: 10px 14px; font-size: 14px; border-bottom: 3px solid transparent; opacity: .85; }
.site-nav a:hover { opacity: 1; }
.site-nav a.active { border-bottom-color: var(--gold); opacity: 1; font-weight: 600; }

/* ---------- main ---------- */
main { flex: 1; padding: 28px 20px 48px; }
h1 { font-size: 26px; margin: 0 0 8px; }
h2 { font-size: 19px; margin: 28px 0 10px; }
.lead { color: var(--muted); margin-top: 0; }
.muted { color: var(--muted); font-weight: normal; font-size: 14px; }
small.muted { font-size: 15px; }
.banner { background: #fff8e1; border: 1px solid #f6d46a; color: #6b4d00; padding: 10px 14px; border-radius: 8px; margin-bottom: 18px; }

table { width: 100%; border-collapse: collapse; background: var(--card); border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--line); font-size: 14.5px; }
th { background: #f1ede8; color: var(--muted); font-weight: 600; font-size: 13px; }
tr:last-child td { border-bottom: none; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }

.btn { display: inline-block; padding: 8px 16px; border-radius: 8px; border: 1px solid var(--maroon); background: var(--maroon); color: #fff; font-size: 14px; text-decoration: none; cursor: pointer; }
.btn.ghost { background: #fff; color: var(--maroon); }
.field { margin-bottom: 14px; }
.field label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 4px; }
.field input, .field select, .field textarea { width: 100%; max-width: 380px; padding: 8px 10px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; font-family: inherit; }

.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
.stat { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; }
.stat .label { color: var(--muted); font-size: 13px; }
.stat .value { font-size: 26px; font-weight: 700; color: var(--maroon); }

.empty { color: var(--muted); padding: 32px; text-align: center; background: var(--card); border: 1px dashed var(--line); border-radius: 10px; }

/* home */
.hero { padding: 8px 0 20px; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 18px; text-decoration: none; color: var(--ink); display: flex; flex-direction: column; gap: 4px; transition: transform .1s, box-shadow .1s; }
.card:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(0,0,0,.07); }
.card-kicker { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .5px; }
.card-title { font-size: 17px; font-weight: 600; color: var(--maroon); }

/* team */
.member-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 8px; }
.member { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 18px; text-align: center; }
.avatar { width: 56px; height: 56px; border-radius: 50%; background: var(--maroon); color: #fff; font-size: 24px; font-weight: 700; display: flex; align-items: center; justify-content: center; margin: 0 auto 10px; }
.member-name { font-weight: 600; }
.role { color: var(--maroon); font-size: 13px; margin-top: 4px; }
.task { color: var(--muted); font-size: 13px; }

/* gallery */
.gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 14px; }
.gallery figure { margin: 0; background: var(--card); border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
.gallery img { width: 100%; height: 140px; object-fit: cover; display: block; }
.gallery figcaption { padding: 8px 10px; font-size: 13.5px; }

/* not built */
.notbuilt { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 28px; }
.notbuilt .reason { font-size: 16px; }
.notbuilt pre { background: #1f2933; color: #f8fafc; padding: 12px; border-radius: 8px; overflow-x: auto; font-size: 12.5px; }
.notbuilt code { background: #f1ede8; padding: 1px 6px; border-radius: 4px; }
.hint { color: var(--muted); font-size: 14px; }

/* footer */
.site-footer { border-top: 1px solid var(--line); color: var(--muted); font-size: 13px; padding: 12px 0; background: #fff; }
.site-footer .wrap { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; }

@media (max-width: 640px) {
  .brand-line1 { font-size: 14px; }
  .brand-line2 { display: none; }
  .group-badge { display: none; }
}


/* ---------- components you can use on any page ---------- */
/* panel / card */
.panel { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 18px; }
.two-col { display: grid; grid-template-columns: 2fr 1fr; gap: 18px; align-items: start; }
@media (max-width: 720px) { .two-col { grid-template-columns: 1fr; } }
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 14px; }
.item-card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; overflow: hidden; display: flex; flex-direction: column; }
.item-card img { width: 100%; height: 140px; object-fit: cover; background: #f1ede8; }
.item-card .body { padding: 12px 14px; display: flex; flex-direction: column; gap: 4px; flex: 1; }
.item-card .price { font-weight: 700; color: var(--maroon); font-size: 18px; margin-top: auto; }
/* badges & pills */
.badge { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 12px; font-weight: 600; background: #f1ede8; color: var(--muted); }
.badge.good { background: #e6f5ec; color: #1b6b3a; }
.badge.bad { background: #fdecec; color: #9b1c1c; }
.badge.gold { background: #fff5d6; color: #8a6100; }
.pills { display: flex; gap: 6px; flex-wrap: wrap; margin: 10px 0; }
.pills a { padding: 5px 12px; border-radius: 999px; border: 1px solid var(--line); background: #fff; color: var(--ink); text-decoration: none; font-size: 13px; }
.pills a.active { background: var(--maroon); border-color: var(--maroon); color: #fff; }
/* stat card variants */
.stat.good .value { color: #1b6b3a; }
.stat.bad .value { color: #9b1c1c; }
.stat.gold { background: #fffbe8; border-color: #f2df9a; }
.stat .unit { color: var(--muted); font-size: 12px; }
/* horizontal bars: width = percent of the biggest value (compute the % in Python) */
.bar-row { display: grid; grid-template-columns: 120px 1fr 90px; align-items: center; gap: 10px; padding: 6px 0; }
.bar-track { background: #efeae4; border-radius: 6px; height: 14px; overflow: hidden; }
.bar-fill { background: var(--maroon); height: 100%; border-radius: 6px; }
.bar-fill.gold { background: var(--gold); }
.bar-fill.green { background: #2e8b57; }
.bar-row .num { text-align: right; font-variant-numeric: tabular-nums; }
/* progress bar */
.progress { background: #efeae4; border-radius: 999px; height: 12px; overflow: hidden; }
.progress > div { background: var(--gold); height: 100%; border-radius: 999px; }
/* vertical columns chart: height = percent (compute the % in Python) */
.chart { display: flex; align-items: flex-end; gap: 8px; height: 180px; padding: 8px 0; border-bottom: 1px solid var(--line); }
.chart .col { flex: 1; display: flex; flex-direction: column; justify-content: flex-end; height: 100%; }
.chart .col > div { background: var(--maroon); border-radius: 4px 4px 0 0; }
.chart .col > div.gold { background: var(--gold); }
.chart-labels { display: flex; gap: 8px; }
.chart-labels span { flex: 1; text-align: center; font-size: 12px; color: var(--muted); }
/* buttons */
.btn.small { padding: 4px 10px; font-size: 13px; }
.btn.full { display: block; width: 100%; text-align: center; }
.btn.danger { background: #fff; color: #9b1c1c; border-color: #f3b4b4; }
form.inline { display: inline; }
/* misc */
.kbd { display: inline-block; padding: 2px 8px; border: 1px solid #cbd5e1; border-bottom-width: 3px; border-radius: 6px; background: #fff; font-family: monospace; font-size: 12px; }
.hero-box { background: linear-gradient(135deg, #fff, #f7efe9); border: 1px solid var(--line); border-radius: 14px; padding: 24px; margin-bottom: 18px; }
.note { font-size: 13px; color: var(--muted); }

/* stacked columns: put several <div class="seg"> inside a .col, heights in % of the column */
.chart .col .seg { width: 100%; }
.chart .col .seg.gold { background: var(--gold); }
.chart .col .seg.green { background: #2e8b57; }
/* donut: style="--p: 42" (percent) */
.donut { width: 120px; height: 120px; border-radius: 50%; background: conic-gradient(var(--maroon) calc(var(--p) * 1%), #efeae4 0); display: flex; align-items: center; justify-content: center; }
.donut > span { width: 78px; height: 78px; border-radius: 50%; background: var(--card); display: flex; align-items: center; justify-content: center; font-weight: 700; color: var(--maroon); }
/* small things forms and summaries keep needing */
.thumb { width: 56px; height: 56px; object-fit: cover; border-radius: 8px; background: #f1ede8; }
.field-row { display: flex; gap: 14px; flex-wrap: wrap; align-items: flex-end; }
.field-row .field { margin: 0; }
.sum-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--line); }
.sum-row.total { border: 0; font-size: 18px; font-weight: 700; color: var(--maroon); }
.game-board { display: block; margin: 0 auto; background: #1f2933; border: 4px solid var(--maroon); border-radius: 10px; }
.hud { display: flex; gap: 10px; justify-content: center; margin: 10px 0; }

/* ---------- your own styles below ---------- */

```

## static\img\arduino.svg

```xml

<svg xmlns="http://www.w3.org/2000/svg" width="400" height="280" viewBox="0 0 400 280">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#89f7fe"/><stop offset="1" stop-color="#66a6ff"/></linearGradient></defs>
  <rect width="400" height="280" fill="url(#g)"/>
  <circle cx="200" cy="140" r="86" fill="#ffffff" fill-opacity="0.35"/>
  <rect x="120" y="90" width="160" height="100" rx="8" fill="#0d7a83"/><rect x="132" y="100" width="40" height="22" rx="3" fill="#cbd5e1"/><rect x="215" y="100" width="55" height="14" rx="2" fill="#1f2933"/><rect x="215" y="120" width="55" height="14" rx="2" fill="#1f2933"/><rect x="132" y="150" width="60" height="14" rx="2" fill="#1f2933"/><rect x="200" y="140" width="50" height="40" rx="3" fill="#1f2933"/><circle cx="150" cy="180" r="5" fill="#e6b422"/><circle cx="165" cy="180" r="5" fill="#e6b422"/>
</svg>

```

## static\img\badminton.svg

```xml

<svg xmlns="http://www.w3.org/2000/svg" width="400" height="280" viewBox="0 0 400 280">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#84fab0"/><stop offset="1" stop-color="#8fd3f4"/></linearGradient></defs>
  <rect width="400" height="280" fill="url(#g)"/>
  <circle cx="200" cy="140" r="86" fill="#ffffff" fill-opacity="0.35"/>
  <ellipse cx="170" cy="105" rx="40" ry="50" fill="none" stroke="#1f2933" stroke-width="7"/><g stroke="#1f2933" stroke-width="1.5"><path d="M140 85 H200 M135 105 H205 M140 125 H200 M160 60 V150 M180 60 V150"/></g><path d="M190 148 L245 215" stroke="#1f2933" stroke-width="10" stroke-linecap="round"/><g fill="#fff" stroke="#5c6b78" stroke-width="2"><path d="M255 95 L275 60 L290 75 L270 110 Z"/><circle cx="255" cy="100" r="8"/></g>
</svg>

```

## static\img\bike.svg

```xml

<svg xmlns="http://www.w3.org/2000/svg" width="400" height="280" viewBox="0 0 400 280">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fbc2eb"/><stop offset="1" stop-color="#a6c1ee"/></linearGradient></defs>
  <rect width="400" height="280" fill="url(#g)"/>
  <circle cx="200" cy="140" r="86" fill="#ffffff" fill-opacity="0.35"/>
  <g fill="none" stroke="#1f2933" stroke-width="7"><circle cx="140" cy="170" r="42"/><circle cx="260" cy="170" r="42"/><path d="M140 170 L185 105 L245 105 L260 170 M185 105 L205 170 L140 170 M205 170 L245 105"/><path d="M235 90 L255 90 M175 100 L190 100"/></g><circle cx="205" cy="170" r="8" fill="#e6b422"/>
</svg>

```

## static\img\book.svg

```xml

<svg xmlns="http://www.w3.org/2000/svg" width="400" height="280" viewBox="0 0 400 280">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f6d365"/><stop offset="1" stop-color="#fda085"/></linearGradient></defs>
  <rect width="400" height="280" fill="url(#g)"/>
  <circle cx="200" cy="140" r="86" fill="#ffffff" fill-opacity="0.35"/>
  <rect x="140" y="90" width="120" height="100" rx="6" fill="#7a1f2b"/><rect x="150" y="82" width="120" height="100" rx="6" fill="#fff"/><rect x="164" y="98" width="70" height="8" rx="4" fill="#d9d2c9"/><rect x="164" y="116" width="90" height="6" rx="3" fill="#e5e0da"/><rect x="164" y="130" width="80" height="6" rx="3" fill="#e5e0da"/><rect x="164" y="144" width="60" height="6" rx="3" fill="#e5e0da"/>
</svg>

```

## static\img\calculator.svg

```xml

<svg xmlns="http://www.w3.org/2000/svg" width="400" height="280" viewBox="0 0 400 280">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#a1c4fd"/><stop offset="1" stop-color="#c2e9fb"/></linearGradient></defs>
  <rect width="400" height="280" fill="url(#g)"/>
  <circle cx="200" cy="140" r="86" fill="#ffffff" fill-opacity="0.35"/>
  <rect x="155" y="70" width="90" height="140" rx="10" fill="#1f2933"/><rect x="165" y="82" width="70" height="28" rx="4" fill="#cfe8c8"/><g fill="#e5e7eb"><rect x="165" y="120" width="18" height="16" rx="3"/><rect x="191" y="120" width="18" height="16" rx="3"/><rect x="217" y="120" width="18" height="16" rx="3"/><rect x="165" y="144" width="18" height="16" rx="3"/><rect x="191" y="144" width="18" height="16" rx="3"/><rect x="217" y="144" width="18" height="16" rx="3"/><rect x="165" y="168" width="18" height="16" rx="3"/><rect x="191" y="168" width="18" height="16" rx="3"/></g><rect x="217" y="168" width="18" height="30" rx="3" fill="#e6b422"/>
</svg>

```

## static\img\fan.svg

```xml

<svg xmlns="http://www.w3.org/2000/svg" width="400" height="280" viewBox="0 0 400 280">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#d4fc79"/><stop offset="1" stop-color="#96e6a1"/></linearGradient></defs>
  <rect width="400" height="280" fill="url(#g)"/>
  <circle cx="200" cy="140" r="86" fill="#ffffff" fill-opacity="0.35"/>
  <circle cx="200" cy="120" r="60" fill="none" stroke="#1f2933" stroke-width="6"/><g fill="#5c6b78"><ellipse cx="200" cy="85" rx="14" ry="30"/><ellipse cx="200" cy="155" rx="14" ry="30"/><ellipse cx="165" cy="120" rx="30" ry="14"/><ellipse cx="235" cy="120" rx="30" ry="14"/></g><circle cx="200" cy="120" r="12" fill="#1f2933"/><rect x="194" y="180" width="12" height="40" fill="#1f2933"/><rect x="160" y="218" width="80" height="10" rx="5" fill="#1f2933"/>
</svg>

```

## static\img\hairdryer.svg

```xml

<svg xmlns="http://www.w3.org/2000/svg" width="400" height="280" viewBox="0 0 400 280">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fddb92"/><stop offset="1" stop-color="#d1fdff"/></linearGradient></defs>
  <rect width="400" height="280" fill="url(#g)"/>
  <circle cx="200" cy="140" r="86" fill="#ffffff" fill-opacity="0.35"/>
  <path d="M140 100 Q140 70 175 70 L245 70 Q275 70 275 100 Q275 130 245 130 L175 130 Q140 130 140 100 Z" fill="#7a1f2b"/><circle cx="250" cy="100" r="18" fill="#5c1620"/><path d="M170 128 L155 200 L195 205 L200 130 Z" fill="#1f2933"/><rect x="100" y="90" width="42" height="20" rx="6" fill="#cbd5e1"/>
</svg>

```

## static\img\headphones.svg

```xml

<svg xmlns="http://www.w3.org/2000/svg" width="400" height="280" viewBox="0 0 400 280">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#cfd9df"/><stop offset="1" stop-color="#e2ebf0"/></linearGradient></defs>
  <rect width="400" height="280" fill="url(#g)"/>
  <circle cx="200" cy="140" r="86" fill="#ffffff" fill-opacity="0.35"/>
  <path d="M140 160 V130 A60 60 0 0 1 260 130 V160" fill="none" stroke="#1f2933" stroke-width="10" stroke-linecap="round"/><rect x="122" y="150" width="36" height="56" rx="10" fill="#7a1f2b"/><rect x="242" y="150" width="36" height="56" rx="10" fill="#7a1f2b"/><rect x="130" y="158" width="20" height="40" rx="6" fill="#1f2933"/><rect x="250" y="158" width="20" height="40" rx="6" fill="#1f2933"/>
</svg>

```

## static\img\kettle.svg

```xml

<svg xmlns="http://www.w3.org/2000/svg" width="400" height="280" viewBox="0 0 400 280">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#e0c3fc"/><stop offset="1" stop-color="#8ec5fc"/></linearGradient></defs>
  <rect width="400" height="280" fill="url(#g)"/>
  <circle cx="200" cy="140" r="86" fill="#ffffff" fill-opacity="0.35"/>
  <path d="M150 110 L250 110 L240 200 L160 200 Z" fill="#cbd5e1"/><path d="M150 110 Q200 85 250 110" fill="#94a3b8"/><path d="M250 125 L280 100 L285 112 L255 140 Z" fill="#94a3b8"/><path d="M150 130 Q120 155 152 180" fill="none" stroke="#1f2933" stroke-width="10" stroke-linecap="round"/><circle cx="200" cy="98" r="7" fill="#1f2933"/><rect x="150" y="200" width="100" height="10" rx="5" fill="#1f2933"/>
</svg>

```

## static\img\lamp.svg

```xml

<svg xmlns="http://www.w3.org/2000/svg" width="400" height="280" viewBox="0 0 400 280">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff1a8"/><stop offset="1" stop-color="#ffd166"/></linearGradient></defs>
  <rect width="400" height="280" fill="url(#g)"/>
  <circle cx="200" cy="140" r="86" fill="#ffffff" fill-opacity="0.35"/>
  <path d="M150 130 L200 60 L250 130 Z" fill="#7a1f2b"/><rect x="194" y="130" width="12" height="70" fill="#1f2933"/><rect x="160" y="198" width="80" height="12" rx="6" fill="#1f2933"/><ellipse cx="200" cy="150" rx="55" ry="14" fill="#fff" fill-opacity="0.6"/>
</svg>

```

## static\img\mouse.svg

```xml

<svg xmlns="http://www.w3.org/2000/svg" width="400" height="280" viewBox="0 0 400 280">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#c1dfc4"/><stop offset="1" stop-color="#deecdd"/></linearGradient></defs>
  <rect width="400" height="280" fill="url(#g)"/>
  <circle cx="200" cy="140" r="86" fill="#ffffff" fill-opacity="0.35"/>
  <path d="M155 120 Q155 70 200 70 Q245 70 245 120 L245 170 Q245 210 200 210 Q155 210 155 170 Z" fill="#1f2933"/><path d="M200 70 V130" stroke="#94a3b8" stroke-width="3"/><rect x="195" y="95" width="10" height="24" rx="5" fill="#94a3b8"/>
</svg>

```

## static\img\placeholder.svg

```xml

<svg xmlns="http://www.w3.org/2000/svg" width="400" height="280" viewBox="0 0 400 280">
  <rect width="400" height="280" fill="#f1ede8"/>
  <circle cx="200" cy="120" r="46" fill="#d9d2c9"/>
  <rect x="120" y="180" width="160" height="16" rx="8" fill="#d9d2c9"/>
  <text x="200" y="240" text-anchor="middle" font-family="Segoe UI, sans-serif" font-size="14" fill="#8a8178">ยังไม่มีรูป</text>
</svg>

```

## static\img\shirt.svg

```xml

<svg xmlns="http://www.w3.org/2000/svg" width="400" height="280" viewBox="0 0 400 280">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f5f7fa"/><stop offset="1" stop-color="#c3cfe2"/></linearGradient></defs>
  <rect width="400" height="280" fill="url(#g)"/>
  <circle cx="200" cy="140" r="86" fill="#ffffff" fill-opacity="0.35"/>
  <path d="M150 80 L180 68 Q200 84 220 68 L250 80 L275 115 L245 130 L245 205 L155 205 L155 130 L125 115 Z" fill="#7a1f2b"/><path d="M180 68 Q200 84 220 68 L212 90 L188 90 Z" fill="#5c1620"/><rect x="170" y="140" width="60" height="6" rx="3" fill="#e6b422"/>
</svg>

```

## static\img\tools.svg

```xml

<svg xmlns="http://www.w3.org/2000/svg" width="400" height="280" viewBox="0 0 400 280">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fbd3b3"/><stop offset="1" stop-color="#f6a87c"/></linearGradient></defs>
  <rect width="400" height="280" fill="url(#g)"/>
  <circle cx="200" cy="140" r="86" fill="#ffffff" fill-opacity="0.35"/>
  <g transform="rotate(-35 200 140)"><rect x="190" y="60" width="20" height="120" rx="4" fill="#94a3b8"/><rect x="180" y="170" width="40" height="60" rx="10" fill="#7a1f2b"/><path d="M190 60 L200 45 L210 60 Z" fill="#94a3b8"/></g><g transform="rotate(35 200 140)"><rect x="192" y="60" width="16" height="110" fill="#1f2933"/><rect x="176" y="165" width="48" height="60" rx="10" fill="#e6b422"/></g>
</svg>

```