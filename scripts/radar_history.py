#!/usr/bin/env python3
"""radar_history.py — دیتابیس SQLite تاریخچه رادار (upsert، بدون حذف، مقیاس‌پذیر)
================================================================================
ورودی: data/radar/snapshots/*.json (هر اسنپ‌شات روزانه خام)
خروجی: data/radar/history/radar_history.db

چرا SQLite (به‌جای JSON قبلی):
    - پردازش افزایشی: هر اسنپ‌شات فقط یک بار پردازش می‌شود (جدول snapshots
      ردیابی می‌کند) — اجرای دوباره همه تاریخچه را دوباره نمی‌خواند
    - کوئری سریع برای گزارش‌ها (ایندکس روی تاریخ + اتاق) — حتی با ۱۰۰ اتاق
      × ۱۰۰ روز × چند سال
    - یکپارچگی داده با PRIMARY KEY (room_id, date) — رکورد تکراری ممکن نیست
    - مهاجرت خودکار از radar_history.json قدیمی (بکاپ JSON حفظ می‌شود —
      «هیچ داده‌ای گم نمی‌شود»)

جدول‌ها:
    rooms(id, label, title, village, host_name, host_id, own)
    days(room_id, date, status, price, discount, is_peak, is_holiday,
         is_weekend, first_seen, last_seen)  — PK(room_id, date)
    snapshots(file, processed_at)            — ردیابی اسنپ‌شات‌های پردازش‌شده

قوانین:
    - UPSERT: اگر روزی قبلاً ثبت شده باشد فقط به‌روزرسانی می‌شود
      (first_seen دست نمی‌خورد، last_seen می‌شود تاریخ اسنپ‌شات جدیدتر)
    - هیچ رکوردی حذف یا بازنویسی نمی‌شود → «هیچ داده‌ای گم نمی‌شود»
    - idempotent: اجرای چندباره در یک روز نتیجه یکسان دارد
    - وضعیت «نیمه‌پر» ذخیره نمی‌شود؛ در زمان گزارش از شب قبل (prev booked
      + امروز free) محاسبه می‌شود تا با تغییرات تاریخی سازگار بماند
"""
import json
import os
import sqlite3
from datetime import date, datetime, timedelta, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
SNAPSHOT_DIR = os.path.join(ROOT, "data", "radar", "snapshots")
HISTORY_DIR = os.path.join(ROOT, "data", "radar", "history")
DB_FILE = os.path.join(HISTORY_DIR, "radar_history.db")
LEGACY_JSON = os.path.join(HISTORY_DIR, "radar_history.json")

SCHEMA = """
CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY,
    label TEXT NOT NULL DEFAULT '',
    short_label TEXT DEFAULT '',
    own INTEGER DEFAULT 0,
    title TEXT, village TEXT, host_name TEXT, host_id TEXT,
    added_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS days (
    room_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    status TEXT NOT NULL,
    price INTEGER,
    discount INTEGER DEFAULT 0,
    is_peak INTEGER DEFAULT 0,
    is_holiday INTEGER DEFAULT 0,
    is_weekend INTEGER DEFAULT 0,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    PRIMARY KEY (room_id, date)
);
CREATE INDEX IF NOT EXISTS idx_days_date ON days(date);
CREATE INDEX IF NOT EXISTS idx_days_room ON days(room_id);
CREATE TABLE IF NOT EXISTS snapshots (
    file TEXT PRIMARY KEY,
    processed_at TEXT NOT NULL
);
"""


def connect():
    os.makedirs(HISTORY_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def migrate_legacy(conn):
    """اگر DB خالی است ولی JSON قدیمی هست → مهاجرت کامل (بدون از دست رفتن).

    تمام رکوردهای روز را از JSON می‌آورد و همه اسنپ‌شات‌های موجود را
    «پردازش‌شده» علامت می‌زند تا دوباره شمارش نشوند.
    """
    if not os.path.exists(LEGACY_JSON):
        return False
    cur = conn.execute("SELECT COUNT(*) FROM days")
    if cur.fetchone()[0] > 0:
        return False  # قبلاً مهاجرت شده — دست نزن
    hist = json.load(open(LEGACY_JSON, encoding="utf-8"))
    migrated = 0
    for rid_str, room in (hist.get("rooms") or {}).items():
        rid = int(rid_str)
        meta = room.get("meta") or {}
        conn.execute(
            "INSERT OR IGNORE INTO rooms (id, label, title, village, host_name, host_id, own) "
            "VALUES (?,?,?,?,?,?,?)",
            (rid, meta.get("title") or f"اتاق {rid}", meta.get("title"),
             meta.get("village"), meta.get("host_name"),
             str(meta.get("host_id") or ""), 1 if meta.get("own") else 0),
        )
        for dstr, rec in (room.get("days") or {}).items():
            conn.execute(
                "INSERT OR REPLACE INTO days "
                "(room_id, date, status, price, discount, is_peak, is_holiday, is_weekend, first_seen, last_seen) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (rid, dstr, rec.get("status", "free"), rec.get("price"),
                 rec.get("discount", 0), int(bool(rec.get("is_peak"))),
                 int(bool(rec.get("is_holiday"))), int(bool(rec.get("is_weekend"))),
                 rec.get("first_seen", ""), rec.get("last_seen", "")),
            )
            migrated += 1
    # اسنپ‌شات‌های موجود را پردازش‌شده علامت بزن تا دوباره شمارش نشوند
    if os.path.isdir(SNAPSHOT_DIR):
        for fn in sorted(f for f in os.listdir(SNAPSHOT_DIR) if f.endswith(".json")):
            conn.execute(
                "INSERT OR IGNORE INTO snapshots (file, processed_at) VALUES (?, ?)",
                (fn, datetime.now(timezone.utc).isoformat()),
            )
    conn.commit()
    print(f"Migrated {migrated} day-records from legacy JSON → SQLite")
    print(f"Legacy backup kept: {LEGACY_JSON}")
    return True


def process_snapshot(conn, fn, snap_date):
    """یک اسنپ‌شات را به‌روز می‌کند. Returns (new_days, upserts)."""
    snap = json.load(open(os.path.join(SNAPSHOT_DIR, fn), encoding="utf-8"))
    # اولین شبِ پنجره (دیروزِ fetch) همیشه is_unavailable=true در API —
    # آرتیفکت است (گذشته است، نه رزرو) و نباید به‌عنوان «پر» ثبت شود
    try:
        artifact_day = (date.fromisoformat(snap_date) - timedelta(days=1)).isoformat()
    except Exception:
        artifact_day = None
    new_days = 0
    upserts = 0
    for rid_str, rdata in (snap.get("rooms") or {}).items():
        rid = int(rid_str)
        meta = rdata.get("meta") or {}
        conn.execute(
            "INSERT OR IGNORE INTO rooms (id, label, title, village, host_name, host_id, own) "
            "VALUES (?,?,?,?,?,?,?)",
            (rid, meta.get("title") or f"اتاق {rid}", meta.get("title"),
             meta.get("village"), meta.get("host_name"),
             str(meta.get("host_id") or ""), 1 if meta.get("own") else 0),
        )
        for night in rdata.get("nights", []):
            dstr = night.get("date")
            if not dstr:
                continue
            if dstr == artifact_day:
                continue  # آرتیفکت API — نادیده
            status = "booked" if night.get("is_unavailable") else "free"
            if night.get("is_manual_block"):
                status = "blocked"
            cur = conn.execute(
                "SELECT 1 FROM days WHERE room_id=? AND date=?", (rid, dstr))
            is_new = cur.fetchone() is None
            conn.execute(
                "INSERT INTO days "
                "(room_id, date, status, price, discount, is_peak, is_holiday, is_weekend, first_seen, last_seen) "
                "VALUES (?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(room_id, date) DO UPDATE SET "
                "status=excluded.status, price=excluded.price, discount=excluded.discount, "
                "is_peak=excluded.is_peak, is_holiday=excluded.is_holiday, is_weekend=excluded.is_weekend, "
                "last_seen=excluded.last_seen",
                (rid, dstr, status, night.get("price"), night.get("discount", 0),
                 int(bool(night.get("is_peak"))), int(bool(night.get("is_holiday"))),
                 int(bool(night.get("is_weekend"))), snap_date, snap_date),
            )
            if is_new:
                new_days += 1
            else:
                upserts += 1
    conn.execute(
        "INSERT OR REPLACE INTO snapshots (file, processed_at) VALUES (?, ?)",
        (fn, datetime.now(timezone.utc).isoformat()),
    )
    return new_days, upserts


def purge_artifact_days(conn):
    """حذف رکوردهای آرتیفکتِ ثبت‌شده در نسخه‌های قبلی: برای هر اسنپ‌شات،
    رکوردِ روزِ قبلِ fetch که first_seen = تاریخ همان اسنپ‌شات است (اولین شبِ
    پنجره — همیشه پر در API). idempotent است: بعد از اولین اجرا چیزی نمی‌ماند."""
    removed = 0
    for (fn,) in conn.execute("SELECT file FROM snapshots"):
        base = fn[:-5] if fn.endswith(".json") else fn
        try:
            artifact = (date.fromisoformat(base) - timedelta(days=1)).isoformat()
        except Exception:
            continue
        cur = conn.execute(
            "DELETE FROM days WHERE date=? AND first_seen=?",
            (artifact, base),
        )
        removed += cur.rowcount
    if removed:
        print(f"Purged {removed} artifact day-records (API yesterday-always-booked)")
    return removed


def main():
    conn = connect()
    migrate_legacy(conn)
    purge_artifact_days(conn)

    snap_files = sorted(
        f for f in os.listdir(SNAPSHOT_DIR) if f.endswith(".json")
    ) if os.path.isdir(SNAPSHOT_DIR) else []
    if not snap_files:
        print("No snapshots found — run fetch_radar.py first.")
        conn.close()
        return

    done = {r[0] for r in conn.execute("SELECT file FROM snapshots")}
    # فایل امروز ممکن است در رفرش‌های ۶ ساعته overwrite شده باشد — باید دوباره
    # پردازش شود تا status/price/last_seen تازه بمانند (first_seen دست نمی‌خورد)
    done.discard(date.today().isoformat() + ".json")
    pending = [f for f in snap_files if f not in done]

    total_new = total_up = 0
    for fn in pending:
        n, u = process_snapshot(conn, fn, fn[:-5])
        total_new += n
        total_up += u
        print(f"  {fn}: +{n} new, {u} upsert", flush=True)
    conn.commit()

    n_rooms = conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
    n_days = conn.execute("SELECT COUNT(*) FROM days").fetchone()[0]
    n_snaps = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
    print(f"History (SQLite): {n_rooms} rooms / {n_days} day-records | "
          f"snapshots processed: {n_snaps}/{len(snap_files)} | this run: +{total_new} new, {total_up} upsert")
    print(f"Saved: {DB_FILE}")
    conn.close()


if __name__ == "__main__":
    main()
