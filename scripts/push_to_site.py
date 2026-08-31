#!/usr/bin/env python3
"""
push_to_site.py — Push a dashboard file to aminsia.ir chalet panel.

Called after build steps in radar_daily.py or standalone.
Usage: python push_to_site.py radar.html
       python push_to_site.py expenses.html
       python push_to_site.py rezerv.html
"""
import os
import sys
import json
import urllib.request
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
    """Push a local file to the site."""
    if target is None:
        target = DASHBOARD_MAP.get(os.path.basename(filepath))
    if target is None:
        print(f"❌ Unknown file: {filepath} — cannot map to target", file=sys.stderr)
        return False

    with open(filepath, "rb") as f:
        data = f.read()
    if len(data) < 1000:
        print(f"❌ File too small ({len(data)} bytes) — skipping", file=sys.stderr)
        return False

    endpoint = f"{URL}/index.php?chalet_cmd=push_dash&target={target}&s={SECRET}"
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "text/html"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if body.get("ok"):
                print(f"✅ pushed {target}: {body['bytes']} bytes (sha:{body['sha']})")
                return True
            else:
                print(f"❌ push failed: {body}", file=sys.stderr)
                return False
    except Exception as e:
        print(f"❌ push error: {e}", file=sys.stderr)
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: push_to_site.py <file> [target]")
        print("  file   — path to dashboard HTML")
        print("  target — radar.html | expenses.html | rezerv.html (auto-detected if omitted)")
        sys.exit(1)

    filepath = sys.argv[1]
    target = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.isfile(filepath):
        print(f"❌ File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    ok = push_file(filepath, target)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
