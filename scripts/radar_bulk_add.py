#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""radar_bulk_add.py — افزودن گروهی همه اتاق‌های داشبورد درآمد به رادار رقبا
===========================================================================
ورودی: data/revenue/seydkola-mordad-1405.json (۳۳ اقامتگاه)
خروجی: data/radar/radar-config.json (اتاق‌های جدید اضافه می‌شوند)

فقط اتاق‌هایی که هنوز در کانفیگ نیستند اضافه می‌شوند (idempotent).
برچسب کوتاه تلگرام از جدول پیشنهادی (تأیید کاربر) یا نام میزبان.

استفاده:
    python scripts/radar_bulk_add.py --dry-run   # پیش‌نمایش بدون ذخیره
    python scripts/radar_bulk_add.py             # اعمال
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from radar_common import CONFIG_FILE, load_config, save_config  # noqa: E402

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
REVENUE_FILE = os.path.join(ROOT, "data", "revenue", "seydkola-mordad-1405.json")
PRICING_FILE = os.path.join(ROOT, "data", "pricing", "pricing-dataset.json")
SUPPLY_FILE = os.path.join(ROOT, "data", "supply-data.json")

# برچسب‌های کوتاه تأییدشده — میزبان‌های تکراری با نوع اقامتگاه تفکیک شده‌اند
SHORT_LABELS = {
    3219516: "عاطفه ویلا",
    3206720: "عاطفه چوبی",
    3178910: "محمد ویلا",
    3190552: "صدیقه",
    3253520: "کاظم سوئیسی",
    3299045: "حبیب ویلا",
    3227770: "محمد خانه",
    3184142: "کاظم چوبی",
    3190700: "لیلا چوبی",
    3206573: "ابوالفضل",
    3198301: "م.ر سوئدی",
    3195220: "م.ر سنتی",
    3198234: "م.ر سوئدی۲",
    3195933: "م.ر سوئیسی",
    3179404: "م.ر چوبی",
    3149747: "میراحسان",
    3201318: "فائزه",
    3237859: "حبیب سوئیسی",
    3149749: "میراحسان سوئیت",
    3232816: "م.ر خانه",
    3262853: "فائزه خانه",
    3193646: "امیرحسین",
    3230216: "حسین ویلا",
    3302232: "بهنام",
}


def load_meta():
    """روستا + میزبان از دیتاست‌های محلی (فقط برای پیش‌نمایش)."""
    meta = {}
    for f in (PRICING_FILE, SUPPLY_FILE):
        try:
            data = json.load(open(f, encoding="utf-8"))
            rooms = data.get("rooms") if isinstance(data, dict) else data
            for r in rooms or []:
                rid = r.get("id")
                if rid and rid not in meta and (r.get("village") or r.get("host_name")):
                    meta[rid] = (r.get("village"), r.get("host_name"))
        except Exception:
            continue
    return meta


def main():
    ap = argparse.ArgumentParser(description="افزودن گروهی اتاق‌های درآمد به رادار")
    ap.add_argument("--dry-run", action="store_true", help="فقط پیش‌نمایش؛ ذخیره نکند")
    args = ap.parse_args()

    revenue = json.load(open(REVENUE_FILE, encoding="utf-8"))
    if not isinstance(revenue, list) or not revenue:
        print(f"❌ فایل درآمد خالی است: {REVENUE_FILE}")
        sys.exit(1)

    cfg = load_config()
    existing = {r["id"] for r in cfg.get("rooms", [])}
    meta = load_meta()

    new_rooms = []
    for rec in revenue:
        rid = rec["id"]
        if rid in existing:
            continue
        title = rec.get("title") or f"اتاق {rid}"
        short = SHORT_LABELS.get(rid)
        if not short:
            m = meta.get(rid)
            short = (m[1] or "").split()[0] if m and m[1] else str(rid)
        new_rooms.append({
            "id": rid,
            "label": title,
            "short_label": short,
            "own": False,
        })

    if not new_rooms:
        print("ℹ️  هیچ اتاق جدیدی برای افزودن نیست — همه از قبل در کانفیگ هستند.")
        return

    print(f"اتاق‌های جدید: {len(new_rooms)}")
    print("=" * 70)
    for r in new_rooms:
        m = meta.get(r["id"])
        v, h = m if m else ("؟", "؟")
        print(f"  {r['id']} | {r['label'][:45]:45s} | {v}/{h} | short={r['short_label']}")
    print("=" * 70)

    if args.dry_run:
        print("(dry-run — چیزی ذخیره نشد)")
        return

    cfg.setdefault("rooms", []).extend(new_rooms)
    save_config(cfg)
    print(f"✅ {len(new_rooms)} اتاق به {CONFIG_FILE} اضافه شد (مجموع: {len(cfg['rooms'])})")


if __name__ == "__main__":
    main()
