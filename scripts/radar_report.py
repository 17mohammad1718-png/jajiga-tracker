#!/usr/bin/env python3
"""
radar_report.py — گزارش درخواستی از دیتابیس تاریخچه رادار
===========================================================
منبع: data/radar/history/radar_history.db (SQLite — منبع واحد؛ همان دیتابیسی
که radar_history.py می‌نویسد و داشبورد تب دیتابیس از آن می‌خواند). هر اتاق ×
هر روز با وضعیت + قیمت + تخفیف ثبت شده.

خروجی پیش‌فرض: جدول ماتریسی (ردیف=اتاق، ستون=روز) — همان سبک گزارش تلگرام
خروجی --list: یک خط برای هر اتاق×روز (جزئیات کامل + نیمه‌پر)

استفاده:
    python scripts/radar_report.py                  # 7 روز اخیر
    python scripts/radar_report.py --days 14        # 14 روز اخیر
    python scripts/radar_report.py --room 3293951   # فقط یک اتاق
    python scripts/radar_report.py --days 30 --list # ردیف به ردیف
    python scripts/radar_report.py --csv out.csv    # خروجی CSV
"""
import argparse
import csv
import os
import sqlite3
import sys
from datetime import date, timedelta

from radar_common import ROOMS, LABELS, JM, g2j, j_dm, j_dmy, weekday_idx, price_m, eff_price

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
HISTORY_DB = os.path.join(ROOT, "data", "radar", "history", "radar_history.db")

WEEK_DAYS_FA = ['شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه']
STATUS_FA = {"booked": "پر", "free": "خالی"}


def load_history():
    """خواندن تاریخچه از SQLite — شکل خروجی همان JSON قدیمی است تا بقیه کد
    تغییری نکند: hist["rooms"][str(rid)]["days"][dstr] = rec."""
    if not os.path.exists(HISTORY_DB):
        print("دیتابیس تاریخچه وجود ندارد — اول radar_history.py اجرا شود.", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(HISTORY_DB)
    conn.row_factory = sqlite3.Row
    hist = {"rooms": {}}
    for row in conn.execute("SELECT * FROM days ORDER BY date"):
        rid = str(row["room_id"])
        room = hist["rooms"].setdefault(rid, {"days": {}})
        room["days"][row["date"]] = {
            "status": row["status"],
            "price": row["price"],
            "discount": row["discount"],
            "is_peak": bool(row["is_peak"]),
            "is_holiday": bool(row["is_holiday"]),
            "is_weekend": bool(row["is_weekend"]),
            "first_seen": row["first_seen"],
            "last_seen": row["last_seen"],
        }
    conn.close()
    return hist


def status_display(dstr, rec, prev_rec):
    """وضعیت نمایشی: اگر شب قبل پر و امروز خالی → نیمه‌پر (turnover)."""
    if rec["status"] == "free" and prev_rec and prev_rec["status"] == "booked":
        return "نیمه‌پر"
    return STATUS_FA.get(rec["status"], rec["status"])


def build_rows(hist, room_ids, dates):
    rooms = hist.get("rooms", {})
    rows = []
    for rid in room_ids:
        room = rooms.get(str(rid))
        if not room:
            continue
        days = room.get("days", {})
        label = LABELS.get(rid, str(rid))
        for i, d in enumerate(dates):
            dstr = d.isoformat()
            rec = days.get(dstr)
            if not rec:
                continue
            prev = days.get(dates[i - 1].isoformat()) if i > 0 else None
            rows.append({
                "room_id": rid,
                "room_label": label,
                "date": dstr,
                "jalali": j_dmy(dstr),
                "weekday": WEEK_DAYS_FA[weekday_idx(d)],
                "status": status_display(dstr, rec, prev),
                "price": rec.get("price"),
                "discount": rec.get("discount", 0),
                "peak": rec.get("is_peak", False),
                "holiday": rec.get("is_holiday", False),
                "weekend": rec.get("is_weekend", False),
                "first_seen": rec.get("first_seen"),
                "last_seen": rec.get("last_seen"),
            })
    return rows


def matrix_report(rows, dates):
    """جدول ماتریسی: ردیف=اتاق، ستون=روز. سلول: █=پر ·=خالی ═=نیمه‌پر + قیمت."""
    CW = 12

    def cell(r):
        if r["status"] == "پر":
            mark = "█"
        elif r["status"] == "نیمه‌پر":
            mark = "═"
        else:
            mark = "·"
        pr = f"{price_m(eff_price(r['price'], r['discount']))}M" if r.get("price") else ""
        return (f"{mark}{pr}")[:CW].ljust(CW)

    by_room = {}
    for r in rows:
        by_room.setdefault(r["room_id"], {})[r["date"]] = r
    date_strs = [d.isoformat() for d in dates]

    header = "┌──┬" + "┬".join("─" * CW for _ in dates) + "┬──────┐"
    sub = ("│# │" + "│".join(
        f"{WEEK_DAYS_FA[weekday_idx(d)][:2]} {j_dm(d.isoformat())}".ljust(CW) for d in dates
    ) + "│ مجموع│")
    sep = "├──┼" + "┼".join("─" * CW for _ in dates) + "┼──────┤"
    lines = []
    for idx, rid in enumerate(by_room, 1):
        room_map = by_room[rid]
        cells = [cell(room_map.get(ds)) if room_map.get(ds) else "".ljust(CW) for ds in date_strs]
        full = sum(1 for c in cells if c.strip().startswith("█"))
        own = "✨" if rid in [r["id"] for r in ROOMS if r.get("own")] else " "
        lines.append(f"│{own}{idx}│" + "│".join(cells) + f"│ {full}  │")
    return "```\n" + header + "\n" + sub + "\n" + sep + "\n" + "\n".join(lines) + "\n" + header + "\n```"


def main():
    ap = argparse.ArgumentParser(description="گزارش تاریخچه رادار رقبا")
    ap.add_argument("--days", type=int, default=7, help="چند روز اخیر (پیش‌فرض 7)")
    ap.add_argument("--room", type=int, default=None, help="فقط یک اتاق")
    ap.add_argument("--list", action="store_true", help="خروجی ردیف به ردیف به جای ماتریس")
    ap.add_argument("--csv", default=None, help="مسیر فایل CSV")
    args = ap.parse_args()

    hist = load_history()
    today = date.today()
    dates = [today - timedelta(days=i) for i in range(args.days - 1, -1, -1)]
    room_ids = [args.room] if args.room else [r["id"] for r in ROOMS]

    rows = build_rows(hist, room_ids, dates)
    if not rows:
        print("رکوردی در این بازه نیست.")
        return

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["room_id", "room_label", "date", "jalali", "weekday",
                                              "status", "price", "discount", "peak", "holiday",
                                              "weekend", "first_seen", "last_seen"])
            w.writeheader()
            w.writerows(rows)
        print(f"CSV saved: {args.csv} ({len(rows)} rows)")

    if args.list:
        for r in rows:
            extra = []
            if r["peak"]:
                extra.append("پیک")
            if r["holiday"]:
                extra.append("تعطیل")
            if r["weekend"]:
                extra.append("آخر هفته")
            disc = f" (-{r['discount']}%)" if r.get("discount") else ""
            print(f"{r['jalali']} {r['weekday']} | {r['room_label']} | {r['status']} | "
                  f"{price_m(eff_price(r['price'], r['discount']))}M{disc}" + (f" | {' '.join(extra)}" if extra else ""))
    else:
        print(matrix_report(rows, dates))
        print("`█`=پر · `·`=خالی · `═`=نیمه‌پر · قیمت به میلیون تومان")


if __name__ == "__main__":
    main()
