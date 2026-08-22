"""
Server for Jajiga Tracker Dashboard
Usage: python server.py
Then open: http://localhost:8080

API:
    GET  /api/edits   → data/radar/manual-edits.json (ویرایش‌های دستی رادار)
    POST /api/edits   → merge + ذخیره اتمیک (بدون بازنویسی رکوردهای جدیدتر)
"""

import http.server
import json
import os
import sys
import threading

# Windows console uses cp1252 by default; emoji in print() would crash it.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass  # Python < 3.7 or non-text stream

PORT = 8080
DIR = os.path.dirname(os.path.abspath(__file__))
EDITS_FILE = os.path.join(DIR, "data", "radar", "manual-edits.json")

_edits_lock = threading.Lock()


def load_edits():
    try:
        with open(EDITS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_edits(edits):
    os.makedirs(os.path.dirname(EDITS_FILE), exist_ok=True)
    tmp = EDITS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(edits, f, ensure_ascii=False, indent=1)
    os.replace(tmp, EDITS_FILE)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)

    def end_headers(self):
        # CORS for local dev
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/edits":
            with _edits_lock:
                edits = load_edits()
            self._send_json({"edits": edits})
            return
        super().do_GET()

    def do_POST(self):
        if self.path.split("?")[0] != "/api/edits":
            self._send_json({"error": "not found"}, status=404)
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw.decode("utf-8"))
            incoming = payload.get("edits") if isinstance(payload, dict) else payload
            if not isinstance(incoming, dict):
                raise ValueError("edits must be an object")
        except Exception as e:
            self._send_json({"error": f"bad request: {e}"}, status=400)
            return

        with _edits_lock:
            current = load_edits()
            merged = 0
            for k, v in incoming.items():
                if not isinstance(v, dict) or not (v.get("s") or v.get("p") is not None):
                    continue
                cur = current.get(k)
                # رکورد جدیدتر برنده است؛ قدیمی‌ترها نادیده (چند مرورگر همزمان)
                if not cur or (v.get("t") or 0) >= (cur.get("t") or 0):
                    current[k] = v
                    merged += 1
            save_edits(current)
        self._send_json({"ok": True, "total": len(current), "merged": merged})

    def log_message(self, fmt, *args):
        pass  # بی‌صدا — لاگ کنسول شلوغ نشود


if __name__ == '__main__':
    print(f"\n  🏡 Jajiga Tracker Dashboard")
    print(f"  ─────────────────────────")
    print(f"  📂 Serving: {DIR}")
    print(f"  🌐 Open:    http://localhost:{PORT}/competitor-radar.html")
    print(f"  ✏️  Edits:   http://localhost:{PORT}/api/edits  → {os.path.relpath(EDITS_FILE, DIR)}")
    print(f"  ⏹  Ctrl+C to stop\n")

    server = http.server.HTTPServer(('0.0.0.0', PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  👋 Server stopped.")
        server.server_close()
