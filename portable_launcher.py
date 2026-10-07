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