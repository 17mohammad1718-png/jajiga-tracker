#!/usr/bin/env python3
"""build_prices_csv.py — خروجی دوم: prices.csv (فقط اقامتگاه‌های اصلی = کلبه‌ها)
بازه‌های یکسان برای همه: یک وسط‌هفته + یک آخر هفته غیرتعطیل، ۲ شب، ۴ مهمان.
انتخاب بازه‌ها داده‌محور: پرچم is_weekend خود جاجیگا + چک is_holiday در داده.
خروجی: فرمت long — هر (اقامتگاه، بازه) یک ردیف. ناموجود = خالی + ستون وضعیت.
"""
import csv, glob, json, os, statistics
from datetime import date, timedelta

ROOT = r"H:/projects/jajiga-tracker"
N_DIR = os.path.join(ROOT, "data", "competitive", "nights")
OUT_DIR = os.path.join(ROOT, "exports", "competitive_2026-09-08")
TODAY = date(2026, 9, 8)
GUESTS, NIGHTS = 4, 2

# ---------- انتخاب بازه‌ها از داده واقعی ----------
# همه پرچم‌های is_weekend/is_holiday را جمع می‌کنیم تا ببینیم جاجیگا کدام روزهای هفته را
# «آخر هفته» می‌داند و آیا تاریخ‌های کاندید پرچم تعطیل دارند.
flags = {}   # date -> {weekend: n, holiday: n, total: n}
for p in glob.glob(os.path.join(N_DIR, "*.json")):
    d = json.load(open(p, encoding="utf-8"))
    for nt in d.get("nights") or []:
        dt = nt.get("date")
        if not dt: continue
        f = flags.setdefault(dt, {"w": 0, "h": 0, "n": 0})
        f["n"] += 1
        if nt.get("is_weekend"): f["w"] += 1
        if nt.get("is_holiday"): f["h"] += 1

# روزهای هفته پرچم‌خورده (برای شفافیت در README)
by_wd = {}
for dt, f in flags.items():
    wd = date.fromisoformat(dt).weekday()   # 0=Mon
    s = by_wd.setdefault(wd, {"w": 0, "n": 0})
    s["n"] += f["n"]; s["w"] += f["w"]
wd_share = {wd: round(s["w"]/max(s["n"],1), 2) for wd, s in sorted(by_wd.items())}
print("weekend-flag share by weekday (0=Mon):", wd_share)

# کاندیدها: وسط‌هفته = 2 شب متوالی با سهم weekend=0؛ آخر هفته = 2 شب متوالی با سهم بالا و بدون تعطیل رسمی
def window_stats(d1, d2):
    w = h = n = 0
    for dt in (str(d1), str(d2)):
        f = flags.get(dt)
        if f: n += f["n"]; w += f["w"]; h += f["h"]
    return {"weekend_share": round(w/max(n,1),2), "holiday_n": h, "samples": n}

def find_window(start_from, want_weekend, days_ahead_cap=40):
    d = start_from
    end = TODAY + timedelta(days=days_ahead_cap)
    while d + timedelta(days=NIGHTS) <= end:
        d2 = d + timedelta(days=1)
        st = window_stats(d, d2)
        # هر دو شب باید در داده با نمونه کافی باشند
        if st["samples"] >= 100:
            if want_weekend and st["weekend_share"] >= 0.6 and st["holiday_n"] == 0:
                return d, st
            if not want_weekend and st["weekend_share"] == 0 and st["holiday_n"] == 0:
                return d, st
        d += timedelta(days=1)
    return None, None

# آغاز از ۷ روز بعد (فاصله امن از تورن‌اور)
start = TODAY + timedelta(days=7)
mid_d, mid_st = find_window(start, want_weekend=False)
wk_d, wk_st = find_window(start, want_weekend=True)
print("midweek window:", mid_d, mid_st)
print("weekend window:", wk_d, wk_st)
assert mid_d and wk_d, "window not found"

WINDOWS = [
    ("وسط_هفته", mid_d),
    ("آخر_هفته", wk_d),
]

roster = json.load(open(os.path.join(ROOT, "data", "competitive", "roster.json"), encoding="utf-8"))
main_ids = {e["id"]: e for e in roster["main"]}

COLS = ["شناسه", "عنوان", "روستا", "بازه", "تاریخ_چک_این", "تاریخ_چک_اوت", "تعداد_شب", "مهمان",
        "قیمت_شب_اول", "تخفیف_شب_اول_درصد", "قیمت_شب_دوم", "تخفیف_شب_دوم_درصد",
        "جمع_قبل_تخفیف", "تخفیف_کل", "قیمت_نهایی_دو_شب", "هزینه_نفر_اضافه_تومان",
        "ظرفیت_پایه", "ظرفیت_حداکثر", "یادداشت_ظرفیت", "وضعیت_قیمت", "تاریخ_استخراج"]

rows = []
for p in sorted(glob.glob(os.path.join(N_DIR, "*.json")), key=lambda x: int(os.path.basename(x)[:-5])):
    rid = int(os.path.basename(p)[:-5])
    if rid not in main_ids: continue
    e = main_ids[rid]
    d = json.load(open(p, encoding="utf-8"))
    nmap = {nt.get("date"): nt for nt in (d.get("nights") or [])}

    # ظرفیت از detail (اگر فچ شده)
    det_p = os.path.join(ROOT, "data", "competitive", "details", f"{rid}.json")
    g_base = g_max = extra = None
    if os.path.exists(det_p):
        det = json.load(open(det_p, encoding="utf-8"))
        if not det.get("_http_error"):
            g_base, g_max, extra = det.get("guest_number"), det.get("max_guest_number"), det.get("extra_price")

    cap_note = ""
    if g_base is not None and g_base < GUESTS:
        cap_note = f"ظرفیت پایه {g_base} نفر کمتر از {GUESTS} مهمان استخراج‌شده"

    for wname, d1 in WINDOWS:
        d2 = d1 + timedelta(days=1)
        n1, n2 = nmap.get(str(d1)), nmap.get(str(d2))
        status_parts = []
        if d.get("note"): status_parts.append(d["note"])
        if not n1: status_parts.append(f"تقویم {str(d1)} را ندارد")
        if not n2: status_parts.append(f"تقویم {str(d2)} را ندارد")
        if n1 and n1.get("is_unavailable"): status_parts.append("شب اول بسته")
        if n2 and n2.get("is_unavailable"): status_parts.append("شب دوم بسته")

        def eff(n):
            if not n or n.get("price") is None: return None, None
            pr = n.get("price") or 0
            disc = n.get("discount") or 0
            return pr, disc

        p1, c1 = eff(n1); p2, c2 = eff(n2)
        gross = disc_total = final = ""
        if p1 is not None and p2 is not None and "بسته" not in " ".join(status_parts):
            gross = p1 + p2
            disc_total = round((p1*c1 + p2*c2) / 100)
            final = gross - disc_total

        rows.append({
            "شناسه": rid, "عنوان": e.get("title",""), "روستا": e.get("village",""),
            "بازه": wname,
            "تاریخ_چک_این": str(d1), "تاریخ_چک_اوت": str(d2),
            "تعداد_شب": NIGHTS, "مهمان": GUESTS,
            "قیمت_شب_اول": p1 if p1 is not None else "",
            "تخفیف_شب_اول_درصد": c1 if c1 is not None else "",
            "قیمت_شب_دوم": p2 if p2 is not None else "",
            "تخفیف_شب_دوم_درصد": c2 if c2 is not None else "",
            "جمع_قبل_تخفیف": gross, "تخفیف_کل": disc_total, "قیمت_نهایی_دو_شب": final,
            "هزینه_نفر_اضافه_تومان": extra if extra is not None else "",
            "ظرفیت_پایه": g_base if g_base is not None else "",
            "ظرفیت_حداکثر": g_max if g_max is not None else "",
            "یادداشت_ظرفیت": cap_note,
            "وضعیت_قیمت": "؛ ".join(status_parts) if status_parts else "استخراج شد",
            "تاریخ_استخراج": d.get("fetched_at",""),
        })

out = os.path.join(OUT_DIR, "prices.csv")
with open(out, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
    w.writeheader(); w.writerows(rows)
ok = sum(1 for r in rows if r["وضعیت_قیمت"] == "استخراج شد")
print(f"prices.csv: {len(rows)} rows ({len(rows)//2} rooms), extracted-clean={ok} -> {out}")

# ثبت بازه‌های انتخاب‌شده برای README
json.dump({"midweek": {"checkin": str(mid_d), **(mid_st or {})},
           "weekend": {"checkin": str(wk_d), **(wk_st or {})},
           "weekend_flag_share_by_weekday": wd_share},
          open(os.path.join(OUT_DIR, "_windows.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
