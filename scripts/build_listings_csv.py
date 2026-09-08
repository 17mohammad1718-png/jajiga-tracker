#!/usr/bin/env python3
"""build_listings_csv.py — خروجی اول: listings.csv
هر ردیف یک اقامتگاه. مقدار ناموجود = خالی. ارقام انگلیسی. UTF-8 BOM.
داده مشاهده‌شده از API؛ هیچ فیلدی حدس زده نمی‌شود.
"""
import csv, glob, json, os, re

ROOT = r"H:/projects/jajiga-tracker"
DET = os.path.join(ROOT, "data", "competitive", "details")
OUT_DIR = os.path.join(ROOT, "exports", "competitive_2026-09-08")
os.makedirs(OUT_DIR, exist_ok=True)

CANCEL_FA = {"easy": "آسان", "middle": "متوسط", "hard": "سخت"}
ALLOCATION_FA = {"entire_place": "دربست", "shared_place": "مشترک (فضای مشترک با میزبان یا مهمان دیگر)"}

def v(x):
    """خروجی تمیز: None/''/0-بولت → خالی"""
    if x is None: return ""
    if isinstance(x, str):
        x = x.strip()
        return x or ""
    return x

def clean_html(t):
    if not t: return ""
    return re.sub(r"<[^>]+>", " ", t)

TYPE_FA = {"wooden_cottage": "کلبه چوبی", "swiss_cottage": "کلبه سوئیسی", "cottage": "کلبه",
           "ecolog": "اقامتگاه بوم‌گردی", "suite": "سوئیت", "apartment": "آپارتمان",
           "ruralhome": "خانه روستایی", "villa": "ویلا"}

def cabin_type(d):
    ts = [TYPE_FA.get(t, t) for t in (d.get("types") or []) if t in TYPE_FA]
    return "، ".join(ts)

roster = json.load(open(os.path.join(ROOT, "data", "competitive", "roster.json"), encoding="utf-8"))
cat_map = {e["id"]: e for lst in ("main", "other", "around") for e in roster[lst]}
BOUNDS_FILE = os.path.join(ROOT, "data", "competitive", "review_bounds.json")
BOUNDS = json.load(open(BOUNDS_FILE, encoding="utf-8")) if os.path.exists(BOUNDS_FILE) else {}

COLS = ["شناسه", "لینک_مستقیم", "عنوان", "روستا", "روستا_مطمئن", "دسته_پرونده", "نوع_مبهم", "نوع_کلبه_از_API",
        "متراژ_بنا_م2", "متراژ_زمین_م2", "تعداد_اتاق_خواب", "ظرفیت_پایه", "ظرفیت_حداکثر",
        "امتیاز_کلی", "تعداد_نظرات_API", "امتیاز_دقت", "امتیاز_ارتباط", "امتیاز_پاکیزگی",
        "امتیاز_موقعیت", "امتیاز_تحویل", "امتیاز_ارزش", "تاریخ_اولین_نظر", "تاریخ_آخرین_نظر",
        "نشان_ها", "میزبان_نام", "میزبان_عضویت_از", "میزبان_نرخ_پذیرش_درصد", "میزبان_زمان_پاسخ_دقیقه",
        "حداقل_شب", "حداکثر_شب", "شرایط_لغو", "ملک_دربست_یا_مشترک", "هزینه_نفر_اضافه_تومان",
        "جکوزی", "محل_جکوزی", "استخر", "گرمایش_استخر", "چشم_انداز_جنگل", "چشم_انداز_رودخانه",
        "حیاط_اختصاصی_محصور", "حریم_خصوصی", "حضور_میزبان_یا_واحد_دیگر", "پارکینگ", "کیفیت_مسیر",
        "اینترنت_وای_فای", "سرمایش", "گرمایش", "حیوان_خانگی", "موقعیت_توضیح", "طول_جغرافیایی", "عرض_جغرافیایی",
        "وضعیت_API", "منابع_شناسایی"]

rows = []
files = sorted(glob.glob(os.path.join(DET, "*.json")), key=lambda p: int(os.path.basename(p)[:-5]))
for p in files:
    d = json.load(open(p, encoding="utf-8"))
    rid = int(os.path.basename(p)[:-5])
    e = cat_map.get(rid, {})
    if d.get("_http_error"):
        rows.append({"شناسه": rid, "لینک_مستقیم": f"https://www.jajiga.com/room/{rid}",
                     "عنوان": e.get("title", ""), "روستا": e.get("village", ""),
                     "روستا_مطمئن": "بله" if e.get("village_confident") else "نامطمئن",
                     "دسته_پرونده": e.get("category", ""),
                     "وضعیت_API": f"خطا {d['_http_error']}",
                     "منابع_شناسایی": "، ".join(e.get("sources", []))})
        continue

    rating = d.get("ratings") or {}
    # امتیاز بدون نظر تعریف‌نشدنی است → خالی (صفر ساختگی جاجیگا)
    n_reviews = rating.get("count")
    def rr(x):
        return v(x) if n_reviews else ""
    host = d.get("host") or {}
    feats = {f.get("name"): (f.get("description") or "") for f in (d.get("features") or [])}
    props = [pr.get("name") if isinstance(pr, dict) else str(pr) for pr in (d.get("properties") or [])]
    rules = set(d.get("rules") or [])
    desc = clean_html(d.get("description") or "")

    # نشان‌ها
    badges = []
    if d.get("is_plus"): badges.append("اقامتگاه پلاس")
    if d.get("is_instant"): badges.append("رزرو فوری")
    if d.get("is_new"): badges.append("تازه ثبت‌شده")
    if d.get("is_clean"): badges.append("میزبان منظم")
    for pr in props:
        if pr in ("اقامتگاه خاص", "لوکس"): badges.append(pr)
    if d.get("video_url"): badges.append("ویدیو دارد")
    if d.get("vr_photo"): badges.append("تور مجازی")

    # جکوزی/استخر: فقط منابع صریح
    jac = feats.get("jacuzzi") is not None or "جکوزی" in desc
    pool_feature = feats.get("pool") is not None
    pool_props = [x for x in props if x in ("استخر آب گرم", "استخر سرپوشیده", "استخر روباز")]
    pool = pool_feature or bool(pool_props) or "استخر" in desc
    # محل جکوزی / گرمایش استخر فقط از متن صریح
    jac_loc = ""
    m = re.search(r"جکوزی[^.\n]{0,80}", desc)
    if m: jac_loc = m.group(0)[:100]
    for s in (feats.get("jacuzzi") or "").split("،"):
        pass
    if feats.get("jacuzzi"):
        jac_loc = feats["jacuzzi"][:120]
    pool_heat = ""
    m = re.search(r"استخر[^.\n]{0,100}(گرم|شوفاژ|از کف|اب گرم|آب گرم)[^.\n]{0,40}", desc)
    if m: pool_heat = m.group(0)[:140]

    forest = ("جنگل" in desc) or any("منظره" in x or "خوش منظره" in x for x in props) and False
    # چشم‌انداز فقط توصیف صریح:
    forest_view = bool(re.search(r"(چشم\s?انداز|ویو|منظره)[^.\n]{0,50}جنگل", desc)) or bool(re.search(r"جنگل[^.\n]{0,50}(چشم\s?انداز|ویو|منظره)", desc))
    river_view = bool(re.search(r"(کنار|لب|حاشیه|رو به|مشرف به)[^.\n]{0,20}(رود|رودخانه)", desc)) or bool(re.search(r"رودخانه[^.\n]{0,40}(کنار|لب|رو به|مشرف)", desc))
    fenced = bool(re.search(r"(حیاط|محوطه)[^.\n]{0,40}(محصور|دیوار|حصار|درب بسته|کاملا (بسته|محصور))", desc)) or "حیاط دار" in props
    privacy = ""
    m = re.search(r"(حریم|دنج|خلوت|مست)[^.\n]{0,60}", desc)
    if m: privacy = m.group(0)[:100]

    parking = feats.get("parking") is not None
    wifi = feats.get("wifi") is not None
    heating = feats.get("heating", "")
    cooling = feats.get("cooler", "")
    pet = "pet" in rules

    row = {
        "شناسه": rid,
        "لینک_مستقیم": d.get("url") or f"https://www.jajiga.com/room/{rid}",
        "عنوان": d.get("title") or e.get("title", ""),
        "روستا": e.get("village", ""),
        "روستا_مطمئن": "بله" if e.get("village_confident") else "نامطمئن",
        "دسته_پرونده": e.get("category", ""),
        "نوع_مبهم": "بله - عنوان هم کلبه هم ویلا" if e.get("ambiguous") else "",
        "نوع_کلبه_از_API": cabin_type(d),
        "متراژ_بنا_م2": v(d.get("floor_area")),
        "متراژ_زمین_م2": v(d.get("land_area")),
        "تعداد_اتاق_خواب": v(d.get("bedrooms")),
        "ظرفیت_پایه": v(d.get("guest_number")),
        "ظرفیت_حداکثر": v(d.get("max_guest_number")),
        "امتیاز_کلی": rr(rating.get("total")),
        "تعداد_نظرات_API": v(rating.get("count")),
        "امتیاز_دقت": rr(rating.get("accuracy")),
        "امتیاز_ارتباط": rr(rating.get("communication")),
        "امتیاز_پاکیزگی": rr(rating.get("cleanliness")),
        "امتیاز_موقعیت": rr(rating.get("location")),
        "امتیاز_تحویل": rr(rating.get("checkin")),
        "امتیاز_ارزش": rr(rating.get("value")),
        "تاریخ_اولین_نظر": BOUNDS.get(str(rid), {}).get("first", ""),
        "تاریخ_آخرین_نظر": BOUNDS.get(str(rid), {}).get("last", ""),
        "نشان_ها": "؛ ".join(badges),
        "میزبان_نام": host.get("name", ""),
        "میزبان_عضویت_از": (host.get("created_at") or "")[:10],
        "میزبان_نرخ_پذیرش_درصد": v(host.get("accept_rate")),
        "میزبان_زمان_پاسخ_دقیقه": v(host.get("response_time")),
        "حداقل_شب": v(d.get("stays_min")),
        "حداکثر_شب": v(d.get("stays_max")),
        "شرایط_لغو": CANCEL_FA.get(d.get("cancellation_policy"), d.get("cancellation_policy") or ""),
        "ملک_دربست_یا_مشترک": ALLOCATION_FA.get(d.get("allocation"), d.get("allocation") or ""),
        "هزینه_نفر_اضافه_تومان": v(d.get("extra_price")),
        "جکوزی": "دارد" if jac else "",
        "محل_جکوزی": jac_loc,
        "استخر": "دارد" if pool else "",
        "گرمایش_استخر": pool_heat,
        "چشم_انداز_جنگل": "ذکر شده" if forest_view else "",
        "چشم_انداز_رودخانه": "ذکر شده" if river_view else "",
        "حیاط_اختصاصی_محصور": "ذکر شده" if fenced else "",
        "حریم_خصوصی": privacy,
        "حضور_میزبان_یا_واحد_دیگر": ALLOCATION_FA.get(d.get("allocation"), "") if d.get("allocation") == "shared_place" else "",
        "پارکینگ": "ذکر شده" if parking else "",
        "کیفیت_مسیر": "",
        "اینترنت_وای_فای": "ذکر شده" if wifi else (feats.get("wifi") or ""),
        "سرمایش": cooling,
        "گرمایش": heating,
        "حیوان_خانگی": "پذیرش (قانون صریح)" if pet else "",
        "موقعیت_توضیح": (d.get("meta") or "")[:200] if isinstance(d.get("meta"), str) else "",
        "طول_جغرافیایی": (d.get("geo") or {}).get("lng") if d.get("geo") else "",
        "عرض_جغرافیایی": (d.get("geo") or {}).get("lat") if d.get("geo") else "",
        "وضعیت_API": d.get("status") or "",
        "منابع_شناسایی": "، ".join(e.get("sources", [])),
    }
    rows.append(row)

out = os.path.join(OUT_DIR, "listings.csv")
cat_of = {}
for e in roster["main"]:   cat_of[e["id"]] = "main"
for e in roster["other"]:  cat_of[e["id"]] = "other"
for e in roster["around"]: cat_of[e["id"]] = "around"
parts = {"main": [], "other": [], "around": []}
for r in rows:
    parts.setdefault(cat_of.get(r.get("شناسه"), "around"), []).append(r)
for name, lst in parts.items():
    fn = {"main": "listings.csv", "other": "listings_other_villa_rustic.csv", "around": "listings_around.csv"}[name]
    out = os.path.join(OUT_DIR, fn)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader(); w.writerows(lst)
    print(f"{fn}: {len(lst)} rows")
err_rows = sum(1 for r in rows if str(r.get("وضعیت_API", "")).startswith("خطا"))
print(f"api-error rows total: {err_rows}")
