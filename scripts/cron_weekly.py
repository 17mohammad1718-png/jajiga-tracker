#!/usr/bin/env python3
"""
Weekly cron entry point for the Jajiga tracker.

Runs the API scraper (quiet), rebuilds the dashboard HTML, then prints a
compact Persian report that gets delivered to the user.

Exit codes: 0 = success, 1 = update failed (cron surfaces it as an alert).
"""
import os
import subprocess
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
PY = sys.executable


def run(script, *args):
    return subprocess.run(
        [PY, os.path.join(SCRIPT_DIR, script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=PROJECT_ROOT,
    )


def main():
    print("Jajiga weekly update starting...", flush=True)

    update = run("weekly_update.py", "--quiet")
    print(update.stdout, end="")
    if update.returncode != 0:
        print("ERROR: weekly_update.py failed:")
        print(update.stderr[-3000:] if update.stderr else "(no stderr)")
        sys.exit(1)

    # Parse the REPORT summary line
    summary_line = ""
    for line in update.stdout.splitlines():
        if line.startswith("REPORT:"):
            summary_line = line
            break

    # Rebuild dashboard
    rebuild = run("rebuild_dashboard_data.py")
    if rebuild.returncode != 0:
        print("ERROR: dashboard rebuild failed:")
        print(rebuild.stderr[-2000:] if rebuild.stderr else "(no stderr)")
        sys.exit(1)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print("\n" + "=" * 60)
    print(f"گزارش هفتگی جاجیگا — {today}")
    print(summary_line)
    print("داشبورد: dashboard.html بازسازی شد")
    print("=" * 60)


def main_with_occupancy():
    """Run update + occupancy fetch + dashboard rebuild.

    Self-sufficient: if the full update fails (transient API timeout), retry
    once with --skip-discover (refresh known cabins only). The dashboard is
    always rebuilt; the run exits 0 as long as the rebuild succeeds so a
    transient network stall doesn't surface as a cron error every week.
    """
    print("Jajiga weekly update starting...", flush=True)

    update = run("weekly_update.py", "--quiet")
    print(update.stdout, end="")
    if update.returncode != 0:
        print("WARNING: full update failed; retrying with --skip-discover "
              "(refresh known cabins only):")
        print(update.stderr[-1500:] if update.stderr else "(no stderr)")
        update = run("weekly_update.py", "--quiet", "--skip-discover")
        print(update.stdout, end="")
        if update.returncode != 0:
            print("ERROR: fallback update also failed; continuing with "
                  "existing data:")
            print(update.stderr[-1500:] if update.stderr else "(no stderr)")
        else:
            print("Fallback refresh (--skip-discover) succeeded.")

    summary_line = ""
    for line in update.stdout.splitlines():
        if line.startswith("REPORT:"):
            summary_line = line
            break
    if not summary_line:
        summary_line = "REPORT: update failed — dashboard rebuilt with existing data"

    # Fetch occupancy (calendar API) for all cabins
    occ = run("fetch_occupancy.py")
    print(occ.stdout, end="")
    if occ.returncode != 0:
        print("WARNING: fetch_occupancy.py had issues:")
        print(occ.stderr[-1500:] if occ.stderr else "(no stderr)")

    # Rebuild dashboard
    rebuild = run("rebuild_dashboard_data.py")
    if rebuild.returncode != 0:
        print("ERROR: dashboard rebuild failed:")
        print(rebuild.stderr[-2000:] if rebuild.stderr else "(no stderr)")
        sys.exit(1)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print("\n" + "=" * 60)
    print(f"گزارش هفتگی جاجیگا — {today}")
    print(summary_line)
    print("اشغال ۳۰ روز: محاسبه شد")
    print("داشبورد: dashboard.html بازسازی شد")
    print("=" * 60)


if __name__ == "__main__":
    main_with_occupancy()
