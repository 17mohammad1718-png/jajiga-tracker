#!/usr/bin/env python3
"""
push_to_site.py — Push a dashboard file to aminsia.ir chalet panel.

Uses curl subprocess (more reliable from Iran VPN than urllib).
Usage: python push_to_site.py radar.html
"""
import os
import sys
import json
import subprocess

URL = "https://aminsia.ir"
SECRET = "CHALET_UPGRADE_2026_AMIN"

DASHBOARD_MAP = {
    "competitor-radar.html": "radar.html",
    "radar.html": "radar.html",
    "dashboard.html": "expenses.html",
    "expenses.html": "expenses.html",
    "rezerv.html": "rezerv.html",
}


def push_file(filepath, target=None):
    if target is None:
        target = DASHBOARD_MAP.get(os.path.basename(filepath))
    if target is None:
        print(f"❌ Unknown file: {filepath}", file=sys.stderr)
        return False

    with open(filepath, "rb") as f:
        data = f.read()
    if len(data) < 1000:
        print(f"❌ File too small ({len(data)} bytes)", file=sys.stderr)
        return False

    endpoint = f"{URL}/index.php?chalet_cmd=push_dash&target={target}&s={SECRET}"

    # Write body to temp file
    import tempfile
    tmp_fd, tmp = tempfile.mkstemp(suffix=".push", prefix="chalet_push_")
    os.close(tmp_fd)
    with open(tmp, "wb") as f:
        f.write(data)

    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "90",
             "-H", "Content-Type: text/html",
             "--data-binary", f"@{tmp}",
             "-o", "-", "-w", "\\nHTTP:%{http_code}",
             endpoint],
            capture_output=True, text=True, timeout=120,
        )
        parts = r.stdout.strip().rsplit("\n", 1)
        body = parts[0] if len(parts) > 1 else ""
        code = parts[1] if len(parts) > 1 else "?"
        result = json.loads(body)
        if result.get("ok"):
            print(f"✅ pushed {target}: {result['bytes']} bytes (sha:{result['sha']})")
            return True
        else:
            print(f"❌ push error: {result}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"❌ push exception: {e}", file=sys.stderr)
        return False
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def main():
    if len(sys.argv) < 2:
        print("Usage: push_to_site.py <file> [target]")
        sys.exit(1)
    filepath = sys.argv[1]
    target = sys.argv[2] if len(sys.argv) > 2 else None
    if not os.path.isfile(filepath):
        print(f"❌ Not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    sys.exit(0 if push_file(filepath, target) else 1)


if __name__ == "__main__":
    main()
