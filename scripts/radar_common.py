#!/usr/bin/env python3
"""radar_common.py — تعاریف مشترک رادار رقبا (اتاق‌ها + ابزار شمسی)
=================================================================
اتاق‌ها از data/radar/radar-config.json خوانده می‌شوند (منبع واحد — با
scripts/radar_add_room.py اضافه می‌شوند؛ بدون دست زدن به کد). اگر فایل
کانفیگ نباشد، با لیست پیش‌فرض ساخته می‌شود تا همه اسکریپت‌ها کار کنند.

هر اتاق در کانفیگ:
    {"id": 3297585, "label": "کلبه سوئیسی (من)", "short_label": "خودت", "own": true}
"""
import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
CONFIG_FILE = os.path.join(ROOT, "data", "radar", "radar-config.json")

# اتاق‌های پیش‌فرض — فقط برای ساخت اولیه کانفیگ (بعداً کانفیگ منبع است)
DEFAULT_ROOMS = [
    {"id": 3297585, "label": "کلبه سوئیسی (من)", "short_label": "خودت", "own": True},
    {"id": 3293951, "label": "کلبه سوئیسی سیدمهدی", "short_label": "سیدمهدی", "own": False},
    {"id": 3179336, "label": "کلبه جکوزی حسن", "short_label": "حسن", "own": False},
    {"id": 3181918, "label": "کلبه جکوزی عیسی", "short_label": "عیسی", "own": False},
    {"id": 3240255, "label": "کلبه استخردار ابراهیم", "short_label": "ابراهیم", "own": False},
    {"id": 3294040, "label": "ویلا محمدرضا", "short_label": "محمدرضا", "own": False},
    {"id": 3240445, "label": "کلبه جکوزی امیر", "short_label": "امیر", "own": False},
    {"id": 3225446, "label": "کلبه جکوزی لیلا", "short_label": "لیلا", "own": False},
    {"id": 3215808, "label": "کلبه جکوزی یوسفعلی", "short_label": "یوسفعلی", "own": False},
    {"id": 3186964, "label": "کلبه جکوزی الناز", "short_label": "الناز", "own": False},
    {"id": 3169804, "label": "ویلا استخردار سیدابراهیم", "short_label": "سیدابراهیم", "own": False},
]


def load_config():
    """کانفیگ رادار را می‌خواند؛ اگر نبود با پیش‌فرض‌ها می‌سازد."""
    if os.path.exists(CONFIG_FILE):
        try:
            return json.load(open(CONFIG_FILE, encoding="utf-8"))
        except Exception:
            pass
    cfg = {"schema_version": 1, "rooms": DEFAULT_ROOMS}
    save_config(cfg)
    return cfg


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# --- بارگذاری یک‌باره: همه اسکریپت‌ها از این متغیرها استفاده می‌کنند ---
_cfg = load_config()
ROOMS = _cfg.get("rooms") or []
ROOM_IDS = [r["id"] for r in ROOMS]
LABELS = {r["id"]: (r.get("label") or f"اتاق {r['id']}") for r in ROOMS}
SHORT_LABELS = {r["id"]: (r.get("short_label") or LABELS[r["id"]]) for r in ROOMS}
OWN_IDS = {r["id"] for r in ROOMS if r.get("own")}

JM = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند']
WD = ['ش','ی','د','س','چ','پ','ج']


def g2j(gy, gm, gd):
    """میلادی → جلالی. خروجی: (سال، ماه، روز)."""
    gdm = [0,31,59,90,120,151,181,212,243,273,304,334]
    gy2 = gy + 1 if gm > 2 else gy
    d = 355666 + 365*gy + (gy2+3)//4 - (gy2+99)//100 + (gy2+399)//400 + gd + gdm[gm-1]
    jy = -1595 + 33*(d//12053); d %= 12053
    jy += 4*(d//1461); d %= 1461
    if d > 365:
        jy += (d-1)//365; d = (d-1)%365
    if d < 186:
        jm = 1 + d//31; jd = 1 + d%31
    else:
        jm = 7 + (d-186)//30; jd = 1 + (d-186)%30
    return jy, jm, jd


def j_dm(dstr):
    """'2026-08-09' → '۱۸ مرداد'"""
    y, m, d = map(int, dstr.split('-'))
    jy, jm, jd = g2j(y, m, d)
    return f"{jd} {JM[jm-1]}"


def j_dmy(dstr):
    """'2026-08-09' → '۱۸ مرداد ۱۴۰۵'"""
    y, m, d = map(int, dstr.split('-'))
    jy, jm, jd = g2j(y, m, d)
    return f"{jd} {JM[jm-1]} {jy}"


def weekday_idx(d):
    """شنبه=0 ... جمعه=6"""
    return (d.weekday() + 2) % 7


def price_m(price):
    """2_400_000 → '2.4' (میلیون) — برای گزارش فشرده تلگرام"""
    if not price:
        return '–'
    s = f"{price/1_000_000:.1f}"
    return s.rstrip('0').rstrip('.')


def eff_price(price, discount):
    """قیمت نهایی پس از اعمال تخفیف — 2_400_000 با 20٪ تخفیف → 1_920_000.

    قیمت API جاجیگا = قیمت پایه است؛ discount درصد تخفیف روی آن است.
    هر جا قیمت نمایش داده می‌شود باید از این تابع استفاده شود (قیمت واقعی).
    """
    if not price:
        return None
    if discount:
        return round(price * (100 - discount) / 100)
    return price
