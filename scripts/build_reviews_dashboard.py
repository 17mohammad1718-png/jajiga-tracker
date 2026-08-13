"""Build a Jajiga review-analysis dashboard (single-file RTL dark HTML).

Usage:
    python scripts/build_reviews_dashboard.py [--room ROOM_ID]

Default room: 3151760 (وانکوه رامسر - the 600-books/402-reviews legend).
Reads reviews from data/reviews/{room}_reviews.json (produced by fetch_reviews.py),
room meta from data/rooms_meta_cache.json (falls back to /api/room/{id} then
data/top_rooms_sweep.json), and writes reviews-dashboard.html at the repo root.
"""
import argparse
import json
import sys
import time
import urllib.request
from collections import Counter
from datetime import date, datetime

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
REVIEWS_DIR = "data/reviews"
CACHE_PATH = "data/rooms_meta_cache.json"
SWEEP_PATH = "data/top_rooms_sweep.json"
OUT_PATH = "reviews-dashboard.html"
DEFAULT_ROOM = 3151760

JM = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد",
      "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]


def g2j(gy, gm, gd):
    """Gregorian -> Jalali (jalaali algorithm, compact)."""
    gdm = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    d = (355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100
         + (gy2 + 399) // 400 + gd + gdm[gm - 1])
    jy = -1595 + 33 * (d // 12053)
    d %= 12053
    jy += 4 * (d // 1461)
    d %= 1461
    if d > 365:
        jy += (d - 1) // 365
        d = (d - 1) % 365
    if d < 186:
        jm = 1 + d // 31
        jd = 1 + d % 31
    else:
        jm = 7 + (d - 186) // 30
        jd = 1 + (d - 186) % 30
    return jy, jm, jd


def jfrom_iso(iso):
    """'2026-08-04T20:30:00Z' -> (jy, jm, jd)."""
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return g2j(dt.year, dt.month, dt.day)


def jdate_str(iso):
    jy, jm, jd = jfrom_iso(iso)
    return f"{jd} {JM[jm-1]} {jy}", f"{iso[:10]}"


def jshort(iso):
    """Short Jalali label for timeline: 'مرداد 05'."""
    jy, jm, _ = jfrom_iso(iso)
    return f"{JM[jm-1]} {jy % 100:02d}"


def api_get(url):
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            if attempt == 3:
                return None
            time.sleep(2 * (attempt + 1))
    return None


# ---------------------------------------------------------------- load data

def load_meta(room_id):
    cache = {}
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            cache = json.load(f)
    except Exception:
        pass
    room_id = str(room_id)
    if room_id in cache:
        return cache[room_id]

    meta = {}
    d = api_get(f"https://api.jajiga.com/api/room/{room_id}")
    if d:
        data = d.get("data", d)
        host = data.get("host") or {}
        meta = {
            "title": data.get("title", ""),
            "host_id": host.get("id"),
            "host_name": host.get("name", ""),
            "host_since": (host.get("created_at") or "")[:10],
            "price": data.get("price"),
            "floor_area": data.get("floor_area"),
            "bedrooms": data.get("bedrooms"),
            "guest_number": data.get("guest_number"),
            "max_guest_number": data.get("max_guest_number"),
            "books": data.get("success_books"),
            "props": [p.get("name") for p in (data.get("properties") or [])],
            "site_rating": None,
            "site_reviews": None,
        }

    # merge search-catalog fields (price often missing in room API)
    try:
        with open(SWEEP_PATH, encoding="utf-8") as f:
            sweep = {str(r["id"]): r for r in json.load(f)}
        if room_id in sweep:
            s = sweep[room_id]
            meta.setdefault("title", s.get("title", ""))
            meta.setdefault("city", s.get("city", ""))
            meta.setdefault("province", s.get("province", ""))
            if meta.get("price") in (None, 0):
                meta["price"] = s.get("price")
            if meta.get("books") in (None, 0):
                meta["books"] = s.get("books")
            meta["site_rating"] = s.get("rating")
            meta["site_reviews"] = s.get("reviews")
    except Exception:
        pass

    if meta:
        cache[room_id] = meta
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=1)
    return meta


def load_reviews(room_id):
    path = f"{REVIEWS_DIR}/{room_id}_reviews.json"
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: {path} not found — run scripts/fetch_reviews.py {room_id} first.")
        sys.exit(1)


# ---------------------------------------------------------------- analytics

CURATED_KW = ["استخر", "جکوزی", "تمیز", "میزبان", "برخورد", "منظره", "طبیعت",
              "جاده", "سکوت", "گرون", "ارزان", "پیشنهاد", "آب گرم", "خوش",
              "متشکر", "تجربه"]
STOPWORDS = {"و", "که", "از", "با", "به", "این", "آن", "بود", "است", "شد",
             "ما", "من", "شما", "هم", "برای", "در", "را", "تا", "همه", "بسیار",
             "بعد", "قبل", "میکنیم", "کرد", "کردم", "کردند", "می", "روی", "شب",
             "روز", "بار", "بارها", "رفتم", "رفتیم", "خودش", "خانه", "اقامتگاه",
             "ویلا", "کلبه", "جا", "جای", "بودن", "داره", "هست", "هستم"}

# Unique-style themes: every theme = a distinctive trait + words that prove it
THEMES = [
    {"key": "gen", "title": "ژنراتور برق — قطعی برق ممنوع",
     "desc": "در بی‌برقی‌های سراسری، اقامتگاه برق دارد",
     "words": ["ژنراتور", "موتور برق", "برق نداره", "قطعی برق", "قطع برق",
               "بی‌برقی", "برق می‌رفت", "برق رفته"]},
    {"key": "pool", "title": "استخر آب گرم روباز",
     "desc": "استخر تمیز با آب گرم، حتی در سرمای زمستان",
     "words": ["استخر", "آب داغ", "آب گرم"]},
    {"key": "view", "title": "ویوی سه‌گانه: دریا + جنگل + کوه",
     "desc": "چشم‌انداز بی‌نظیر از بالکن و استخر",
     "words": ["ویو", "ویوی", "منظره", "چشم‌انداز", "چشم انداز", "دریا", "جنگل"]},
    {"key": "garden", "title": "باغ مرکبات — پرتقال و نارنج",
     "desc": "مهمان‌ها از میوه‌های باغ استفاده می‌کنند",
     "words": ["پرتقال", "نارنج", "مرکبات", "باغ"]},
    {"key": "cats", "title": "گربه‌های دمِ در",
     "desc": "گربه‌های باغ که منتظر مهمان‌ها هستند",
     "words": ["گربه", "گربه‌ها", "گربه ها"]},
    {"key": "host", "title": "میزبانی حرفه‌ای و پیگیر",
     "desc": "پاسخ‌گویی سریع، حتی نیمه‌شب",
     "words": ["میزبان", "مهری", "یاسر", "مالک", "صاحب"]},
    {"key": "hotel", "title": "جزئیات هتلی",
     "desc": "ملافه‌های سفید هتلی + پک بهداشتی",
     "words": ["ملافه", "پک بهداشتی", "هتلی", "اسکاج"]},
    {"key": "loyal", "title": "مشتریان وفادار",
     "desc": "مهمان‌هایی که بارها برمی‌گردند",
     "words": ["باز هم", "بار دوم", "بار سوم", "بار چهارم", "دوبار", "دو بار",
               "پاتوق", "دوباره رزرو", "بازم میام", "باز میام", "دوباره این"]},
    {"key": "road", "title": "دسترسی: ۵۰۰ متر جاده خاکی",
     "desc": "تنها نکتهٔ خاکی مسیر",
     "words": ["جاده", "خاکی", "مسیر", "آسفالت"]},
]

FUN_MARKERS = ["نمره 20", "نمره ۲۰", "هزار ویلا", "پاتوق", "گربه", "موریانه",
               "کلاس آموزشی", "20 میدم", "۲۰ میدم", "شاهکار", "بهترین ویلای",
               "می‌خند", "😂", "خنده", "پشیمون", "پشیمان", "امتیاز کامل دادم",
               "زیبا گزارش", "جون میده"]


def compute_stats(reviews):
    today = date.today()
    ratings = [r.get("rating", 0) or 0 for r in reviews]
    scored = [x for x in ratings if x > 0]
    dist = Counter(round(x, 1) for x in scored)
    buckets = Counter()
    for x in scored:
        buckets[int(x + 0.5)] += 1  # 4.8,4.5 -> 5 ; 4.2,4.0 -> 4 ; 3.7,3 -> 3

    last_year = [r for r in reviews
                 if date.fromisoformat(r["created_at"][:10]) >=
                 date(today.year - 1, today.month, today.day)]
    ly_ratings = [r.get("rating", 0) or 0 for r in last_year if (r.get("rating") or 0) > 0]
    ly_n = len(ly_ratings)

    def avg(xs):
        return round(sum(xs) / len(xs), 2) if xs else None

    months = Counter(r["created_at"][:7] for r in reviews)
    monthly = [{"key": k, "count": c, "jshort": jshort(k + "-05")}
               for k, c in sorted(months.items())]

    years = Counter()
    for r in reviews:
        years[jfrom_iso(r["created_at"])[0]] += 1

    users = Counter((r.get("user") or {}).get("id") for r in reviews)
    unique = len(users)
    repeat = []
    for uid, c in sorted(users.items(), key=lambda x: -x[1]):
        if c > 1 and uid is not None:
            name = next((r.get("user", {}).get("name", "?")
                         for r in reviews if (r.get("user") or {}).get("id") == uid), "?")
            years_of = sorted({jfrom_iso(r["created_at"])[0]
                               for r in reviews
                               if (r.get("user") or {}).get("id") == uid})
            repeat.append({"name": name, "count": c, "years": years_of})

    texts = " ".join(r.get("content", "") for r in reviews)
    kw_cur = [{"word": w, "count": texts.count(w)} for w in CURATED_KW if texts.count(w) >= 1]
    tokens = Counter(t for t in texts.split() if len(t) > 2 and t not in STOPWORDS)
    kw_auto = [{"word": w, "count": c} for w, c in tokens.most_common(15) if c >= 3]
    # merge curated then auto (dedupe, keep higher count)
    kw = {d["word"]: d["count"] for d in kw_cur}
    for d in kw_auto:
        kw[d["word"]] = max(kw.get(d["word"], 0), d["count"])
    keywords = sorted([{"word": w, "count": c} for w, c in kw.items()],
                      key=lambda x: -x["count"])[:25]

    total = len(reviews)
    five = dist.get(5, 0)
    replied = sum(1 for r in reviews if r.get("host_reply"))

    # ---- unique-style themes (distinctive traits + proof quotes) ----
    themes = []
    for t in THEMES:
        hit = [r for r in reviews if any(w in (r.get("content") or "") for w in t["words"])]

        def _score(r):
            c = (r.get("content") or "").strip()
            L = len(c)
            if not (40 <= L <= 260):
                return 0
            return (10 if (r.get("rating") or 0) == 5 else 4) - abs(L - 150) / 45

        samples = sorted(hit, key=_score, reverse=True)[:3]
        themes.append({
            "key": t["key"], "title": t["title"], "desc": t["desc"],
            "word": t["words"][0], "count": len(hit),
            "samples": [{
                "text": (s.get("content") or "").strip()[:260],
                "rating": s.get("rating"),
                "name": (s.get("user") or {}).get("name"),
                "date": s["created_at"][:10],
            } for s in samples],
        })

    # ---- fun / notable comments (auto-detected, category spread) ----
    fun_raw = []
    for r in reviews:
        c = (r.get("content") or "").strip()
        if not c:
            continue
        tags = []
        if (r.get("rating") or 0) <= 3:
            tags.append("انتقادی")
        if any(ch in c for ch in "😂😍🙏❤️👌🤣🌿✨😅"):
            tags.append("احساسی")
        if len(c) >= 220:
            tags.append("مفصل")
        if any(m in c for m in FUN_MARKERS):
            tags.append("بامزه")
        if tags:
            fun_raw.append({"text": c, "rating": r.get("rating"),
                            "name": (r.get("user") or {}).get("name"),
                            "date": r["created_at"][:10], "tags": tags})
    prio = ["بامزه", "انتقادی", "احساسی", "مفصل"]
    fun = []
    seen_texts = set()
    for tag in prio:
        picked = 0
        for it in fun_raw:
            if len(fun) >= 8:
                break
            if (tag in it["tags"] and it not in fun
                    and it["text"] not in seen_texts):
                it["tag"] = tag
                fun.append(it)
                seen_texts.add(it["text"])
                picked += 1
            if picked >= 2:
                break
        if len(fun) >= 8:
            break
    fun = [{"text": f["text"][:280], "rating": f["rating"], "name": f["name"],
            "date": f["date"], "tag": f["tag"]} for f in fun[:8]]
    return {
        "total": total,
        "avg_all": avg(scored),
        "avg_ly": avg(ly_ratings) if ly_n else None,
        "ly_n": ly_n,
        "dist": {str(k): v for k, v in sorted(dist.items(), reverse=True)},
        "buckets": {str(k): buckets.get(k, 0) for k in range(1, 6)},
        "below5": len(scored) - five,
        "five": five,
        "reply_rate": round(replied * 100 / total),
        "replied": replied,
        "unique_users": unique,
        "repeat_users": repeat[:8],
        "monthly": monthly,
        "years": {str(k): v for k, v in sorted(years.items(), reverse=True)},
        "keywords": keywords,
        "themes": themes,
        "fun": fun,
        "fetched_at_iso": date.today().isoformat(),
    }


# ---------------------------------------------------------------- template

TEMPLATE = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>تحلیل نظرات — __TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;600;800&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0d1117; --panel:#161b22; --panel2:#1c2128; --border:#21262d;
  --text:#e6edf3; --muted:#8b949e; --teal:#2dd4bf; --teal-d:#0d9488;
  --blue:#58a6ff; --orange:#f0883e; --gold:#f0b429; --silver:#a8b3c0; --bronze:#c07a4b;
  --red:#f85149; --green:#3fb950;
}
*{box-sizing:border-box; margin:0; padding:0}
html{scrollbar-gutter:stable}
body{
  background:var(--bg); color:var(--text);
  font-family:'Vazirmatn',Tahoma,sans-serif; line-height:1.7;
  padding:20px 16px 60px;
}
.wrap{max-width:1280px; margin:0 auto}
a{color:var(--blue); text-decoration:none}
a:hover{text-decoration:underline}
.en{font-family:Consolas,'Courier New',monospace; direction:ltr; unicode-bidi:embed;
    letter-spacing:.2px; color:inherit}
h1{font-size:22px; font-weight:800; color:#fff}
h2{font-size:15px; font-weight:700; margin-bottom:10px; color:#fff}
.sub{color:var(--muted); font-size:12px}

/* ---- header / hero ---- */
.hero{
  background:linear-gradient(135deg,#16233a 0%,#0d1117 70%);
  border:1px solid var(--border); border-radius:14px;
  padding:18px 20px; margin-bottom:16px;
}
.hero h1{font-size:21px}
.hero-links{margin:6px 0 10px; font-size:13px}
.host-link{color:var(--orange)!important; font-weight:600}
.chips{display:flex; flex-wrap:wrap; gap:6px; margin-top:10px}
.chip{background:var(--panel2); border:1px solid var(--border); color:var(--text);
      border-radius:999px; padding:2px 12px; font-size:12px}
.chip .en{color:var(--teal)}
.chip.prop{color:#7ee787; border-color:#2d4a2f}

/* ---- KPI cards ---- */
.kpis{display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:10px; margin-bottom:16px}
.kpi{background:var(--panel); border:1px solid var(--border); border-radius:12px; padding:12px 14px}
.kpi .ico{font-size:18px; margin-bottom:2px}
.kpi .v{font-size:21px; font-weight:800; color:#fff}
.kpi .v.en{color:var(--teal); font-size:20px}
.kpi .l{font-size:11.5px; color:var(--muted); margin-top:1px}
.kpi .note{font-size:10.5px; color:var(--muted); margin-top:2px}
.badge{display:inline-block; background:#1f3d33; color:#7ee787; border:1px solid #2d4a2f;
       border-radius:6px; font-size:10.5px; padding:0 6px; margin-right:4px}

/* ---- panels ---- */
.panel{background:var(--panel); border:1px solid var(--border); border-radius:12px;
       padding:14px 16px; margin-bottom:16px}

/* rating dist */
.bars{display:flex; align-items:flex-end; gap:14px; height:190px; padding:0 6px; position:relative; direction:ltr}
.bar-col{flex:1; display:flex; flex-direction:column; align-items:center; justify-content:flex-end; height:100%; position:relative}
.bar{width:min(46px,70%); border-radius:6px 6px 0 0; background:linear-gradient(180deg,#2dd4bf,#0e7490);
     min-height:3px; position:relative}
.bar.b5{background:linear-gradient(180deg,#f0b429,#b45309)}
.bar .bcount{position:absolute; top:-20px; left:50%; transform:translateX(-50%);
             font-size:11px; color:#fff; font-weight:700}
.bar-label{font-size:12px; color:var(--muted); margin-top:6px}
.bar-label .en{color:var(--text)}
.avg-line{position:absolute; left:0; right:0; border-top:2px dashed var(--red); opacity:.75}
.avg-line span{position:absolute; left:6px; top:-19px; font-size:10.5px; color:var(--red);
               background:var(--panel); padding:0 4px; border-radius:4px}

/* timeline */
.tl-scroll{overflow-x:auto; padding-bottom:6px}
.tl{display:flex; align-items:flex-end; gap:3px; min-width:max-content; height:150px; direction:ltr}
.tl-col{display:flex; flex-direction:column; justify-content:flex-end; align-items:center; width:34px}
.tl-bar{width:22px; border-radius:4px 4px 0 0; background:linear-gradient(180deg,#58a6ff,#1f6feb); min-height:3px}
.tl-lbl{font-size:9.5px; color:var(--muted); margin-top:4px; white-space:nowrap; transform:rotate(-35deg); transform-origin:top center}

/* keywords */
.kw{display:flex; align-items:center; gap:10px; margin-bottom:7px; direction:rtl}
.kw-w{width:110px; text-align:right; font-size:13px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis}
.kw-track{flex:1; height:16px; background:#0d1117; border-radius:8px; overflow:hidden; direction:rtl}
.kw-fill{height:100%; background:linear-gradient(90deg,#0e7490,#2dd4bf); border-radius:8px}
.kw-c{width:44px; text-align:left; font-size:12.5px; color:var(--teal)}

/* theme cards (unique style) */
.theme-grid{display:grid; grid-template-columns:repeat(auto-fill,minmax(330px,1fr)); gap:10px}
.theme-card{background:var(--panel2); border:1px solid var(--border); border-radius:10px;
            padding:12px 14px; display:flex; flex-direction:column; gap:7px}
.th-head{display:flex; align-items:center; gap:8px; flex-wrap:wrap}
.th-title{font-size:13.5px; font-weight:700; color:#fff}
.th-count{font-size:11px; color:var(--teal); background:#0d1f1c; border:1px solid #1f4a42;
          border-radius:999px; padding:0 8px; white-space:nowrap}
.th-desc{font-size:11.5px; color:var(--muted)}
.th-quote{font-size:12px; color:var(--text); line-height:1.8; border-right:3px solid var(--teal-d);
          padding:6px 10px; background:#11161d; border-radius:6px; min-height:52px}
.th-quote .q-meta{font-size:10.5px; color:var(--muted); margin-top:2px}
.th-btn{margin-top:2px; background:transparent; border:1px solid var(--border); color:var(--blue);
        border-radius:8px; padding:4px 10px; font-size:12px; cursor:pointer; font-family:inherit}
.th-btn:hover{border-color:var(--blue)}

/* fun comments */
.fun-grid{display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:10px}
.fun-card{background:var(--panel2); border:1px solid var(--border); border-radius:10px;
          padding:12px 14px; display:flex; flex-direction:column; gap:8px}
.fun-tag{font-size:11px; border-radius:999px; padding:1px 10px; align-self:flex-start}
.fun-tag.bamaze{background:#2d3a1f; color:#a3e635; border:1px solid #3f4f2d}
.fun-tag.entegadi{background:#3a1f1f; color:#f85149; border:1px solid #4f2d2d}
.fun-tag.ehsasi{background:#2d2a1f; color:#e3b341; border:1px solid #4f442d}
.fun-tag.mofassal{background:#1f2d3a; color:#58a6ff; border:1px solid #2d4a6f}
.fun-text{font-size:13px; color:var(--text); line-height:1.9; font-style:italic}
.fun-meta{font-size:11.5px; color:var(--muted)}

/* filters */
.filters{display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-bottom:12px}
.fgroup{display:flex; align-items:center; gap:6px}
.fgroup .fl{font-size:12px; color:var(--muted)}
.fbtn{background:var(--panel2); border:1px solid var(--border); color:var(--text);
      border-radius:999px; padding:3px 12px; font-size:12px; cursor:pointer; transition:.15s}
.fbtn:hover{border-color:var(--teal-d)}
.fbtn.on{background:var(--teal-d); color:#fff; border-color:var(--teal-d)}
#searchInput{background:var(--panel2); border:1px solid var(--border); color:var(--text);
             border-radius:8px; padding:5px 12px; font-size:13px; width:220px;
             font-family:inherit}
#searchInput:focus{outline:none; border-color:var(--teal-d)}
.result-count{font-size:12px; color:var(--muted); margin:0 4px 10px}

/* table */
.table-wrap{overflow-x:auto; overflow-y:auto; max-height:85vh; border:1px solid var(--border); border-radius:10px;
            scrollbar-width:thin; scrollbar-color:#475569 #0b1526}
table{width:100%; border-collapse:collapse; font-size:13px; min-width:900px}
thead th{position:sticky; top:0; z-index:5; background:#0f1a2b; color:#c9d1d9;
         text-align:center; padding:9px 8px; border-bottom:2px solid var(--border);
         font-size:12px; cursor:pointer; user-select:none; white-space:nowrap}
thead th:hover{background:#13233a}
thead th .srt{font-size:10px; color:var(--teal)}
tbody td{text-align:center; padding:8px 10px; border-bottom:1px solid var(--border); vertical-align:middle}
tbody tr:nth-child(even){background:#151b23}
tbody tr:hover{background:#1a2230}
td.rev-content{text-align:right; direction:rtl; min-width:320px; max-width:480px;
               overflow-wrap:anywhere; white-space:pre-wrap; line-height:1.8; font-size:12.5px}
td.rev-user{font-weight:600}
.nohr .en{color:var(--text)}
.stars{display:inline-flex; align-items:center; direction:ltr; position:relative; color:#30363d; font-size:13px}
.stars .fill{position:absolute; left:0; top:0; overflow:hidden; white-space:nowrap; color:var(--gold)}
.stars-val{font-size:11.5px; margin-left:6px; color:#fff}
.reply-yes{color:#7ee787; font-size:12px}
.reply-no{color:var(--muted); font-size:12px}
.reply-toggle{display:inline-flex; align-items:center; gap:5px; background:transparent;
  border:1px solid #2d4a2f; color:#7ee787; border-radius:999px; padding:3px 12px;
  font-size:12px; cursor:pointer; font-family:inherit; transition:.15s}
.reply-toggle:hover{border-color:#3fb950; background:#132519}
.reply-toggle .arr{font-size:10px; transition:transform .15s}
.reply-toggle.open .arr{transform:rotate(180deg)}
.reply-detail td{background:#0f1f18; border-bottom:1px solid var(--border); padding:10px 16px}
.reply-box{text-align:right}
.reply-head{font-size:11px; color:#7ee787; font-weight:700; margin-bottom:4px}
.reply-text{font-size:12.5px; color:#c9d1d9; line-height:1.9; white-space:pre-wrap; overflow-wrap:anywhere}
.flash-row{animation:flashRow 2.2s ease}
@keyframes flashRow{0%{background:rgba(45,212,191,.30)}100%{background:transparent}}
.jump-ring{animation:jumpPulse 2.6s ease}
@keyframes jumpPulse{0%{box-shadow:0 0 0 8px rgba(45,212,191,.9)}45%{box-shadow:0 0 0 5px rgba(45,212,191,.5)}100%{box-shadow:0 0 0 2px rgba(45,212,191,.25)}}
.empty td{text-align:center; color:var(--muted); padding:26px}

/* footer */
footer{margin-top:18px; color:var(--muted); font-size:11.5px; text-align:center; line-height:2}

/* dark scrollbar (user standard) */
::-webkit-scrollbar{width:10px; height:10px}
::-webkit-scrollbar-track{background:#0b1526; border-radius:8px}
::-webkit-scrollbar-thumb{background:linear-gradient(180deg,#475569,#334155); border-radius:8px; border:2px solid #0b1526}
::-webkit-scrollbar-thumb:hover{background:linear-gradient(180deg,#5b6f8f,#475569)}
::-webkit-scrollbar-corner{background:#0b1526}
@media (pointer:fine){::-webkit-scrollbar{width:10px; height:10px}}
</style>
</head>
<body>
<div class="wrap">

  <div class="hero">
    <h1 class="rtl">__TITLE__</h1>
    <div class="hero-links">
      <a class="room-link" href="__ROOM_URL__" target="_blank" rel="noopener">صفحه اقامتگاه</a>
      <span style="color:var(--muted)"> · میزبان: </span>
      <a class="host-link" href="__HOST_URL__" target="_blank" rel="noopener">__HOST_NAME__</a>
      <span class="sub" style="margin-right:6px">(عضو از __HOST_SINCE__)</span>
    </div>
    <div class="chips" id="metaChips"></div>
  </div>

  <div class="kpis" id="kpis"></div>

  <div class="panel">
    <h2>توزیع امتیاز نظرات <span class="sub">(بر اساس امتیاز ثبت‌شده در هر نظر)</span></h2>
    <div class="bars" id="rateBars"></div>
    <div class="sub" style="margin-top:30px" id="distNote"></div>
  </div>

  <div class="panel">
    <h2>روند ماهانه نظرات</h2>
    <div class="tl-scroll"><div class="tl" id="timeline"></div></div>
  </div>

  <div class="panel">
    <h2>کلیدواژه‌های پرتکرار در نظرات</h2>
    <div id="keywords"></div>
  </div>

  <div class="panel" id="stylePanel">
    <h2>سبک منحصر به فرد اقامتگاه <span class="sub">(با پیام مهمان‌ها)</span></h2>
    <div class="theme-grid" id="themeGrid"></div>
  </div>

  <div class="panel" id="funPanel">
    <h2>کامنت‌های جالب و نکته‌ها</h2>
    <div class="fun-grid" id="funGrid"></div>
  </div>

  <div class="panel" id="reviewsPanel">
    <h2>همه نظرات</h2>
    <div class="filters">
      <div class="fgroup"><span class="fl">امتیاز:</span><div id="ratingFilters"></div></div>
      <div class="fgroup"><span class="fl">پاسخ میزبان:</span><div id="replyFilters"></div></div>
      <div class="fgroup"><span class="fl">سال شمسی:</span><div id="yearFilters"></div></div>
      <input id="searchInput" type="search" placeholder="جستجو در متن و نام کاربر...">
      <button class="fbtn" id="resetBtn">بازنشانی</button>
    </div>
    <div class="result-count" id="resultCount"></div>
    <div class="table-wrap"><table>
      <thead><tr>
        <th data-col="idx">#</th>
        <th data-col="date">تاریخ <span class="en">(شمسی)</span><span class="srt"></span></th>
        <th data-col="user">کاربر<span class="srt"></span></th>
        <th data-col="rating">امتیاز<span class="srt"></span></th>
        <th>متن نظر</th>
        <th data-col="reply">پاسخ میزبان<span class="srt"></span></th>
      </tr></thead>
      <tbody id="tbody"></tbody>
    </table></div>
  </div>

  <footer id="footerNote"></footer>
</div>

<script type="application/json" id="revdata">__REVDATA__</script>
<script>
const D = JSON.parse(document.getElementById('revdata').textContent);
const R = D.reviews;
const M = D.meta, S = D.stats;

function en(n){ return '<span class="en">' + (n==null?'-':Number(n).toLocaleString('en-US')) + '</span>'; }
function esc(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

/* ---------- meta chips ---------- */
(function(){
  const chips = [];
  if(M.city) chips.push('شهر: ' + esc(M.city));
  if(M.price) chips.push('قیمت: ' + en(M.price) + '<span style="color:var(--muted)"> تومان/شب</span>');
  if(M.floor_area) chips.push('متراژ: ' + en(M.floor_area) + '<span style="color:var(--muted)"> متر</span>');
  if(M.bedrooms!=null) chips.push('خواب: ' + en(M.bedrooms));
  if(M.guest_number!=null) chips.push('ظرفیت: ' + en(M.guest_number) + (M.max_guest_number?' تا '+en(M.max_guest_number):''));
  if(M.books) chips.push('رزرو موفق: ' + en(M.books));
  if(M.site_rating) chips.push('امتیاز نمایشی سایت: ' + en(M.site_rating) + ' <span class="badge">یک سال اخیر</span>');
  chips.push('نظر در کارت سایت: ' + en(M.site_reviews));
  (M.props||[]).forEach(p=>chips.push('<span class="chip prop">'+esc(p)+'</span>'));
  document.getElementById('metaChips').innerHTML = chips.map(c=>'<span class="chip">'+c+'</span>').join('');
})();

/* ---------- KPI ---------- */
(function(){
  const fivePct = Math.round(S.five*100/S.total);
  const kpis = [
    {ico:'💬', v: en(S.total), l:'کل نظرات (از API)', note:'کارت سایت ' + (M.site_reviews||'؟')},
    {ico:'⭐', v: en(S.avg_all), l:'میانگین کل تاریخچه (۶ سال)', note:S.dist?null:'-'},
    {ico:'✨', v: en(S.avg_ly), l:'میانگین ۱ سال اخیر', note:S.ly_n+' نظر · نمایش سایت ' + en(M.site_rating||'') + ' <span class="badge">مبنای نمایش</span>'},
    {ico:'🔝', v: en(S.five) + ' <small class="en" style="font-size:12px;color:var(--gold)">('+fivePct+'%)</small>', l:'نظر با امتیاز کامل', note:'زیر ۵: ' + en(S.below5) + ' نظر'},
    {ico:'💚', v: en(S.replied) + '/' + en(S.total), l:'پاسخ میزبان به نظرات', note:'نرخ: ' + en(S.reply_rate) + '%'},
    {ico:'👥', v: en(S.unique_users), l:'کاربر یکتا', note:'تکرارکننده: ' + en(S.repeat_users.length) + ' نفر'}
  ];
  document.getElementById('kpis').innerHTML = kpis.map(k=>
    '<div class="kpi"><div class="ico">'+k.ico+'</div><div class="v">'+k.v+'</div><div class="l">'+k.l+'</div>'+
    (k.note?'<div class="note">'+k.note+'</div>':'')+'</div>').join('');
})();

/* ---------- rating distribution ---------- */
(function(){
  const max = Math.max(...Object.values(S.buckets));
  const starNames = {5:'پنج',4:'چهار',3:'سه',2:'دو',1:'یک'};
  const el = document.getElementById('rateBars');
  let html = '';
  for(let s=5;s>=1;s--){
    const c = S.buckets[s]||0;
    const h = Math.max(3, Math.round(c/max*150));
    html += '<div class="bar-col"><div class="bar'+(s===5?' b5':'')+'" style="height:'+h+'px">'+
            '<span class="bcount">'+en(c)+'</span></div>'+
            '<div class="bar-label">'+starNames[s]+' <span class="en">★</span></div></div>';
  }
  el.insertAdjacentHTML('afterbegin', html);
  if(S.avg_all){
    const pct = Math.round((S.avg_all-1)/4*100);
    const mark = document.createElement('div');
    mark.className = 'avg-line';
    mark.style.bottom = (pct*1.5)+'px';
    mark.innerHTML = '<span>میانگین ' + en(S.avg_all) + '</span>';
    el.appendChild(mark);
  }
  const d = S.dist||{};
  document.getElementById('distNote').innerHTML =
    'تفکیک دقیق: ' + Object.entries(d).map(([k,v])=>'<span class="en" style="margin:0 4px">'+k+'</span> × '+
    '<span class="en">'+v+'</span>').join(' · ') + ' · بدون امتیاز: <span class="en">' +
    (S.total - Object.values(d).reduce((a,b)=>a+b,0)) + '</span>';
})();

/* ---------- timeline ---------- */
(function(){
  const months = S.monthly;
  const max = Math.max(...months.map(m=>m.count));
  document.getElementById('timeline').innerHTML = months.map(m=>{
    const h = Math.max(3, Math.round(m.count/max*120));
    return '<div class="tl-col" title="'+m.jshort+' — '+m.count+' نظر">'+
           '<div class="tl-bar" style="height:'+h+'px;background:'+
           (m.count===max?'linear-gradient(180deg,#f0b429,#b45309)':'linear-gradient(180deg,#58a6ff,#1f6feb)')+'"></div>'+
           '<div class="tl-lbl">'+m.jshort+'</div></div>';
  }).join('');
})();

/* ---------- keywords ---------- */
(function(){
  const kw = S.keywords;
  if(!kw.length){ document.getElementById('keywords').innerHTML = '<div class="sub">موردی یافت نشد</div>'; return; }
  const max = kw[0].count;
  document.getElementById('keywords').innerHTML = kw.map(k=>
    '<div class="kw"><div class="kw-w">'+esc(k.word)+'</div>'+
    '<div class="kw-track"><div class="kw-fill" style="width:'+Math.round(k.count/max*100)+'%"></div></div>'+
    '<div class="kw-c">'+en(k.count)+'</div></div>').join('');
})();

/* ---------- unique style themes ---------- */
(function(){
  const themes = S.themes||[];
  const ICONS = {gen:'🔌', pool:'🏊', view:'🏔️', garden:'🍊', cats:'🐈',
                 host:'🤝', hotel:'🛏️', loyal:'💛', road:'🛣️'};
  if(!themes.length){ document.getElementById('stylePanel').style.display='none'; return; }
  document.getElementById('themeGrid').innerHTML = themes.map(t=>{
    const quotes = (t.samples||[]).map(q=>
      '<div class="th-quote">'+esc(q.text)+
      '<div class="q-meta">— '+esc(q.name||'؟')+' · <span class="en">'+q.date+'</span> · '+
      '<span class="en">'+(q.rating==null?'-':q.rating)+'</span> ★</div></div>').join('');
    return '<div class="theme-card"><div class="th-head"><span>'+(ICONS[t.key]||'✨')+'</span>'+
      '<div class="th-title">'+esc(t.title)+'</div>'+
      '<span class="th-count"><span class="en">'+t.count+'</span> نظر</span></div>'+
      '<div class="th-desc">'+esc(t.desc)+'</div>'+quotes+
      '<button class="th-btn" data-word="'+esc(t.word)+'">مشاهده همه در جدول ↓</button></div>';
  }).join('');
  document.querySelectorAll('.th-btn').forEach(b=>{
    b.onclick=()=>{
      const w = b.dataset.word;
      state.rating=state.reply=state.year=null; state.col=state.dir=null;
      resetChipUI();
      state.search = w;
      document.getElementById('searchInput').value = w;
      flashOnJump = true;
      render();
      scrollPanelIntoView();
    };
  });
})();

/* ---------- filter UI helpers ---------- */
function resetChipUI(){
  ['ratingFilters','replyFilters','yearFilters'].forEach(id=>{
    document.querySelectorAll('#'+id+' .fbtn').forEach((b,i)=>b.classList.toggle('on', i===0));
  });
}
function scrollPanelIntoView(){
  const panel = document.getElementById('reviewsPanel');
  if(!panel) return;
  const rectTop = panel.getBoundingClientRect().top + (window.scrollY||document.documentElement.scrollTop||0);
  try{ panel.scrollIntoView({behavior:'smooth', block:'start'}); }catch(e){}
  try{ panel.scrollIntoView(true); }catch(e){}
  try{ window.scrollTo({top: Math.max(0, rectTop-14), behavior:'smooth'}); }catch(e){}
  try{ document.documentElement.scrollTop = rectTop-14; }catch(e){}
  try{ document.body.scrollTop = rectTop-14; }catch(e){}
  // the Hermes preview pane renders the file in an iframe sized to content:
  // the real scrollbar lives in the PARENT document, so scroll it too (same-origin file://)
  try{
    const p = window.parent;
    if(p && p.document){
      const innerTop = panel.getBoundingClientRect().top;
      try{ p.scrollTo({top: Math.max(0, (p.scrollY||0) + innerTop - 14), behavior:'smooth'}); }catch(e2){}
    }
  }catch(e3){}
  // flashing ring so the panel is unmistakable
  panel.classList.remove('jump-ring');
  void panel.offsetWidth;
  panel.classList.add('jump-ring');
}

/* ---------- fun / notable comments ---------- */
(function(){
  const fun = S.fun||[];
  const TAG_CLS = {'بامزه':'bamaze','انتقادی':'entegadi','احساسی':'ehsasi','مفصل':'mofassal'};
  if(!fun.length){ document.getElementById('funPanel').style.display='none'; return; }
  document.getElementById('funGrid').innerHTML = fun.map(f=>
    '<div class="fun-card"><span class="fun-tag '+(TAG_CLS[f.tag]||'ehsasi')+'">'+esc(f.tag)+'</span>'+
    '<div class="fun-text">«'+esc(f.text)+'»</div>'+
    '<div class="fun-meta">'+esc(f.name||'؟')+' · <span class="en">'+f.date+'</span> · '+
    '<span class="en">'+(f.rating==null?'-':f.rating)+'</span> ★</div></div>').join('');
})();

/* ---------- table ---------- */
const state = {rating:null, reply:null, year:null, search:'', col:null, dir:null};
let flashOnJump = false;
function rowOf(r){ return {idx:0, date:new Date(r.created_at).getTime(),
  dateISO:r.created_at.slice(0,10), j:r._j, user:(r.user&&r.user.name)||'؟',
  rating:r.rating||0, content:r.content||'', reply:r.host_reply?1:0,
  replyTxt:(r.host_reply&&r.host_reply.content)||'',
  replyDate:((r.host_reply&&r.host_reply.created_at)||'').slice(0,10)}; }

function filtered(){
  let arr = R.map(rowOf);
  if(state.rating) arr = arr.filter(x=>x.rating>=state.rating);
  if(state.reply==='has') arr = arr.filter(x=>x.reply);
  if(state.reply==='none') arr = arr.filter(x=>!x.reply);
  if(state.year) arr = arr.filter(x=>x._jy===state.year);
  if(state.search){
    const q = state.search.toLowerCase();
    arr = arr.filter(x=>x.user.toLowerCase().includes(q)||x.content.toLowerCase().includes(q));
  }
  if(state.col && state.dir){
    const col = state.col;
    const get = col==='date'?x=>x.date : col==='rating'?x=>x.rating :
                col==='user'?x=>x.user : col==='reply'?x=>x.reply : x=>x.idx;
    arr.sort((a,b)=>{ const av=get(a), bv=get(b);
      if(av<bv) return state.dir==='desc'?1:-1;
      if(av>bv) return state.dir==='desc'?-1:1;
      return 0; });
  }
  return arr;
}

function starsStr(rating){
  const pct = Math.max(0, Math.min(100, rating/5*100));
  return '<span class="stars"><span>★★★★★</span><span class="fill" style="width:'+pct+'%">★★★★★</span></span>'+
         '<span class="stars-val">'+en(rating.toFixed(1))+'</span>';
}

function render(){
  const rows = filtered();
  const tbody = document.getElementById('tbody');
  const MAX = 400;
  const shown = rows.length>MAX ? rows.slice(0,MAX) : rows;
  tbody.innerHTML = shown.length ? shown.map((x,i)=>{
    const replyCell = x.reply
      ? '<button class="reply-toggle" data-i="'+i+'">پاسخ میزبان <span class="arr">▾</span></button>'
      : '<span class="reply-no">— بدون پاسخ</span>';
    const detailRow = x.reply
      ? '<tr class="reply-detail" data-i="'+i+'" style="display:none"><td colspan="6">'+
        '<div class="reply-box"><div class="reply-head">پاسخ میزبان — <span class="en">'+(x.replyDate||'')+'</span></div>'+
        '<div class="reply-text">'+esc(x.replyTxt)+'</div></div></td></tr>'
      : '';
    return '<tr class="main-row" data-i="'+i+'"><td class="en">'+(i+1)+'</td>'+
      '<td><div class="en" style="color:#fff">'+x.j+'</div><div class="sub en">'+x.dateISO+'</div></td>'+
      '<td class="rev-user">'+esc(x.user)+'</td>'+
      '<td>'+starsStr(x.rating)+'</td>'+
      '<td class="rev-content">'+esc(x.content)+'</td>'+
      '<td>'+replyCell+'</td></tr>' + detailRow;
  }).join('') : '<tr class="empty"><td colspan="6">موردی یافت نشد</td></tr>';
  // expand/collapse host replies
  tbody.querySelectorAll('.reply-toggle').forEach(btn=>{
    btn.onclick=()=>{
      const i = btn.closest('.main-row').dataset.i;
      const detail = tbody.querySelector('tr.reply-detail[data-i="'+i+'"]');
      const open = detail.style.display==='table-row';
      detail.style.display = open?'none':'table-row';
      btn.classList.toggle('open', !open);
    };
  });
  document.getElementById('resultCount').innerHTML =
    'نمایش <span class="en">'+shown.length+'</span> از <span class="en">'+rows.length+'</span> نظر'+
    (rows.length>MAX?' (بیش از 400 با فیلتر محدود کنید)':'')+
    ' — مجموع نظرات اقامتگاه: <span class="en">'+S.total+'</span>'+
    (state.search ? ' <button class="fbtn on" id="clearTheme">فیلتر: «'+esc(state.search)+'» ✕</button>' : '');
  const clearBtn = document.getElementById('clearTheme');
  if(clearBtn) clearBtn.onclick = ()=>{ state.search=''; document.getElementById('searchInput').value=''; resetChipUI(); render(); };
  if(flashOnJump){
    tbody.querySelectorAll('.main-row').forEach((tr,i)=>{ if(i<5) tr.classList.add('flash-row'); });
    flashOnJump = false;
  }
  document.querySelectorAll('thead th[data-col]').forEach(th=>{
    const srt = th.querySelector('.srt');
    if(th.dataset.col===state.col) srt.textContent = state.dir==='desc'?' ▼':state.dir==='asc'?' ▲':'';
    else srt.textContent = '';
  });
}

/* filters UI */
function chipGroup(containerId, items, active, onPick){
  const c = document.getElementById(containerId);
  c.innerHTML = items.map((it,i)=>
    '<button class="fbtn'+(i===active?' on':'')+'" data-i="'+i+'">'+it.label+'</button>').join('');
  c.querySelectorAll('button').forEach(b=>b.onclick=()=>{ onPick(+b.dataset.i); });
}
(function(){
  const ratingItems = [{v:null,label:'همه'},{v:5,label:'فقط ۵'},{v:4.8,label:'۴.۸ به بالا'},{v:4.5,label:'۴.۵ به بالا'}];
  const replyItems = [{v:null,label:'همه'},{v:'has',label:'دارد'},{v:'none',label:'ندارد'}];
  chipGroup('ratingFilters', ratingItems, 0, i=>{ state.rating=ratingItems[i].v; state.col=state.dir=null; render(); });
  chipGroup('replyFilters', replyItems, 0, i=>{ state.reply=replyItems[i].v; state.col=state.dir=null; render(); });
  const years = Object.keys(S.years).sort((a,b)=>+b-+a);
  const yearItems = [{v:null,label:'همه'}].concat(years.map(y=>({v:+y,label:'<span class="en">'+y+'</span>'})));
  chipGroup('yearFilters', yearItems, 0, i=>{ state.year=yearItems[i].v; state.col=state.dir=null; render(); });
})();
document.getElementById('searchInput').oninput = function(){ state.search=this.value; render(); };
document.getElementById('resetBtn').onclick = function(){
  state.rating=state.reply=state.year=null; state.search=''; state.col=state.dir=null;
  document.getElementById('searchInput').value='';
  render();
};
document.querySelectorAll('thead th[data-col]').forEach(th=>{
  th.onclick = ()=>{
    const col = th.dataset.col;
    if(state.col!==col){ state.col=col; state.dir='desc'; }
    else if(state.dir==='desc'){ state.dir='asc'; }
    else { state.col=null; state.dir=null; }
    render();
  };
});

/* ---------- footer ---------- */
(function(){
  const yrs = (S.repeat_users||[]).map(u=>u.name+' ('+u.count+' نظر)').join('، ');
  let html = 'داده: <span class="en">'+S.fetched_at_iso+'</span> — منبع: <span class="en">api.jajiga.com</span> — '+
    '<span class="en">'+S.total+'</span> نظر از API (کارت سایت '+(M.site_reviews||'؟')+' — '+
    Math.max(0,(M.site_reviews||0)-S.total)+' نظر در API موجود نیست)' +
    (S.repeat_users.length?'<br>کاربران چند نظر: '+esc(yrs):'') ;
  document.getElementById('footerNote').innerHTML = html;
})();

/* precompute per-review Jalali (once) */
(function(){
  const JM=['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];
  function g2j(gy,gm,gd){
    const gdm=[0,31,59,90,120,151,181,212,243,273,304,334];
    const gy2=gm>2?gy+1:gy;
    let d=355666+365*gy+Math.floor((gy2+3)/4)-Math.floor((gy2+99)/100)+Math.floor((gy2+399)/400)+gd+gdm[gm-1];
    let jy=-1595+33*Math.floor(d/12053); d%=12053;
    jy+=4*Math.floor(d/1461); d%=1461;
    if(d>365){ jy+=Math.floor((d-1)/365); d=(d-1)%365; }
    let jm,jd;
    if(d<186){ jm=1+Math.floor(d/31); jd=1+(d%31); }
    else{ jm=7+Math.floor((d-186)/30); jd=1+((d-186)%30); }
    return [jy,jm,jd];
  }
  R.forEach(r=>{
    const [y,m]=r.created_at.slice(0,10).split('-').map(Number);
    const j=g2j(y,m,1);
    const [jy,jm,jd]=g2j(y,m,Number(r.created_at.slice(8,10)));
    r._j = jd+' '+JM[jm-1]+' '+jy;
    r._jy = jy;
  });
})();

render();
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--room", type=int, default=DEFAULT_ROOM)
    args = ap.parse_args()
    room = args.room

    reviews = load_reviews(room)
    meta = load_meta(room)
    stats = compute_stats(reviews)

    title = meta.get("title") or f"اتاق {room}"
    host_name = meta.get("host_name") or "میزبان"
    host_since = (meta.get("host_since") or "")[:10] or "?"
    host_id = meta.get("host_id")

    payload = {
        "room": room,
        "meta": {
            "title": title,
            "city": meta.get("city"),
            "price": meta.get("price"),
            "floor_area": meta.get("floor_area"),
            "bedrooms": meta.get("bedrooms"),
            "guest_number": meta.get("guest_number"),
            "max_guest_number": meta.get("max_guest_number"),
            "books": meta.get("books"),
            "props": meta.get("props") or [],
            "site_rating": meta.get("site_rating"),
            "site_reviews": meta.get("site_reviews"),
            "host_name": meta.get("host_name"),
            "host_id": meta.get("host_id"),
            "host_since": meta.get("host_since"),
        },
        "stats": stats,
        "reviews": reviews,
    }
    payload_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")

    html = (TEMPLATE
            .replace("__TITLE__", title)
            .replace("__ROOM_URL__", f"https://www.jajiga.com/room/{room}")
            .replace("__HOST_URL__", f"https://www.jajiga.com/user/{host_id}" if host_id else "#")
            .replace("__HOST_NAME__", host_name)
            .replace("__HOST_SINCE__", host_since)
            .replace("__REVDATA__", payload_json))

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[OK] {OUT_PATH} — {stats['total']} نظر، میانگین کل {stats['avg_all']}، "
          f"میانگین یک سال اخیر {stats['avg_ly']} ({stats['ly_n']} نظر)، "
          f"پاسخ میزبان {stats['reply_rate']}%")


if __name__ == "__main__":
    main()
