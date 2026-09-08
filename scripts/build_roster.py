#!/usr/bin/env python3
"""build_roster.py — اتحاد همه منابع اتاق‌های بابلکنار + دسته‌بندی کلبه چوبی/سوئیسی
منابع: jajiga.db rooms + top_rooms_sweep + corpus rooms + all-cabins + search-API slugs
خروجی: data/competitive/roster.json  (main / other / around + آمار)
"""
import json, os, re, sqlite3, time, urllib.parse, urllib.request

ROOT = r"H:/projects/jajiga-tracker"
OUT_DIR = os.path.join(ROOT, "data", "competitive")
os.makedirs(OUT_DIR, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
      "Accept": "application/json"}

# روستاهای داخل محدوده (از regions جدول DB + لفور که تابع بابلکنار است)
IN_VILLAGES = {"سیدکلا","سید کلا","قرآن تالار","قران تالار","گونه کلا","گونع کلا","شیردارکلا",
    "چهره","کاردرکلا","کاردکلا","کاردکرکلا","درازکلا","دراز کش","درازکش","سیادرکا","سیادرکلا",
    "رئیس کلا","رئیسکلا","فراملک","بالف کلا","بالفکلا","مرزیکلا","کلاریکلا","کبریاکلا","بزچفت",
    "ممرزکن","فرامرزکلا","امیرکلا","درونکلا","قادیکلا","بابلکنار","لفور","تیرکن"}

WOOD_TOKENS = ["کلبه", "سوئیسی", "سوئدی", "چوبی", "کابین", "cabin", "کللت"]
VILLA_TOKENS = ["ویلا", "خانه روستایی", "خانه مبله", "خانه ویلایی", "سوئیت", "سوییت", "آپارتمان", "خانه تراس", "مهمانپذیر", "بومگردی"]

def title_has_any(t, toks):
    t = t or ""
    return [w for w in toks if w in t]

def classify(title, api_types=None):
    """main=wooden/swiss, other=villa/rustic, around handled by caller"""
    t = title or ""
    wood = title_has_any(t, WOOD_TOKENS)
    villa = title_has_any(t, VILLA_TOKENS)
    types = [str(x).lower() for x in (api_types or [])]
    type_wood = any(x in ("cabin", "cottage", "wooden") for x in types)
    type_villa = any(x in ("villa", "house") for x in types)
    if wood and villa:
        return "main", 1          # ambiguous: claims both
    if wood or type_wood:
        return "main", 0
    if villa or type_villa:
        return "other", 0
    if types:
        return "main", 1          # unknown type → keep, flag
    return "main", 1

def find_village(title, db_village):
    if db_village and db_village in IN_VILLAGES:
        return db_village, 1      # confident (curated DB)
    t = title or ""
    # longest village name found in title
    cands = [v for v in IN_VILLAGES if v in t and v not in ("بابلکنار",)]
    if cands:
        return max(cands, key=len), 1
    if "بابلکنار" in t:
        return "بابلکنار", 0      # claims region, no village → uncertain
    return None, 0

def norm_id(v):
    try: return int(v)
    except Exception: return None

# ---------- 1) DB ----------
con = sqlite3.connect(os.path.join(ROOT, "jajiga.db"))
db_rooms = {}
for rid, title, village, status in con.execute("SELECT id, title, village, status FROM rooms"):
    db_rooms[int(rid)] = {"title": title or "", "village": village or "", "status": status or ""}
con.close()

# ---------- 2) sweep ----------
sweep = json.load(open(os.path.join(ROOT, "data", "top_rooms_sweep.json"), encoding="utf-8"))
sweep_bab = {}
for s in sweep:
    city = (s.get("city") or "").strip()
    title = s.get("title") or ""
    if city == "بابلکنار" or "بابلکنار" in title:
        sweep_bab[int(s["id"])] = {"title": title, "city": city,
                                   "rating": s.get("rating"), "reviews": s.get("reviews"),
                                   "books": s.get("books"), "price": s.get("price"),
                                   "url": s.get("url")}

# ---------- 3) corpus rooms ----------
corpus_rooms = json.load(open(os.path.join(ROOT, "data", "reviews_mining", "manifest.json"), encoding="utf-8"))
corpus_bab = {}
for c in corpus_rooms:
    title = c.get("title") or ""
    city = (c.get("city") or "").strip()
    if city == "بابلکنار" or "بابلکنار" in title or (find_village(title, None)[0] and city in IN_VILLAGES) or any(v in title for v in IN_VILLAGES):
        corpus_bab[int(c["room_id"])] = {"title": title, "city": city,
                                         "card_reviews": c.get("card_reviews")}

# ---------- 4) all-cabins ----------
allc = json.load(open(os.path.join(ROOT, "data", "all-cabins.json"), encoding="utf-8"))
cabins = {}
for vil, lst in allc.get("villages", {}).items():
    for r in lst:
        cabins[int(r["id"])] = {"title": r.get("title") or "", "village": vil,
                                "rating": r.get("rating"), "reviews": r.get("reviews"),
                                "price": r.get("price"), "occupancy_30": r.get("occupancy_30"),
                                "pool": r.get("pool"), "jacuzzi": r.get("jacuzzi")}

# ---------- 5) search-API top-up ----------
def search_slug(path):
    url = ("https://api.jajiga.com/api/search?per_page=18&page=1&url="
           + urllib.parse.quote(path) + "&with[]=rooms")
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read().decode("utf-8"))
        items = (d.get("rooms") or {}).get("items") or []
        return items
    except Exception as e:
        print("  search fail", path, str(e)[:60])
        return []

SLUGS = ["/s/babolkenar/cottage", "/s/seyyedkolababolkenar/cottage", "/s/gonehkola/cottage",
         "/s/qurantalar/cottage", "/s/shirdarkola/cottage", "/s/kaardekola/cottage",
         "/s/marzikola/cottage", "/s/darazkola/cottage", "/s/balefkola/cottage",
         "/s/chehare/cottage", "/s/lavor/cottage"]
search_rooms = {}
for p in SLUGS:
    items = search_slug(p)
    new = 0
    for r in items:
        t = r.get("title") or ""
        if "بابلکنار" in t or (r.get("city_name") or "") == "بابلکنار" or any(v in t for v in IN_VILLAGES):
            if int(r["id"]) not in search_rooms:
                search_rooms[int(r["id"])] = {"title": t, "slug": p,
                                              "city_name": r.get("city_name"),
                                              "rating": (r.get("rating") or {}).get("total") if isinstance(r.get("rating"), dict) else r.get("rating")}
                new += 1
    print(f"slug {p}: {len(items)} items, +{new} new babolkenar")
    time.sleep(1.0)

# ---------- union ----------
union = {}
def put(rid, src, **kw):
    rid = norm_id(rid)
    if not rid: return
    e = union.setdefault(rid, {"id": rid, "sources": set(), "title": "", "village_db": "",
                               "db_status": "", "region_claim": "", "sweep": {}, "corpus": {},
                               "cabin": {}, "search": {}})
    e["sources"].add(src)
    for k, v in kw.items():
        if v not in (None, ""):
            e[k] = v

for rid, r in db_rooms.items():     put(rid, "db", title=r["title"], village_db=r["village"], db_status=r["status"])
# city=بابلکنار در sweep/corpus → ادعای منطقه‌ای قابل اتکا (ولی روستا نامطمئن)
for rid, s in sweep_bab.items():
    put(rid, "sweep", title=s["title"])
    union[rid]["sweep"] = {k: v for k, v in s.items() if k != "title"}
    if s.get("city") == "بابلکنار":
        union[rid]["region_claim"] = "بابلکنار"
for rid, c in corpus_bab.items():
    put(rid, "corpus", title=c["title"])
    union[rid]["corpus"] = {k: v for k, v in c.items() if k != "title"}
    if c.get("city") == "بابلکنار":
        union[rid]["region_claim"] = "بابلکنار"
for rid, c in cabins.items():       put(rid, "cabins", title=c["title"], village_db=c["village"]); union[rid]["cabin"] = {k: v for k, v in c.items() if k not in ("title",)}
for rid, s in search_rooms.items(): put(rid, "search", title=s["title"]); union[rid]["search"] = {k: v for k, v in s.items() if k != "title"}

# normalize sources
for e in union.values():
    e["sources"] = sorted(e["sources"])
    if not e["village_db"] and e.get("cabin", {}).get("village"):
        e["village_db"] = e["cabin"]["village"]

# classify + village
main, other, around = [], [], []
for e in union.values():
    cat, amb = classify(e["title"])
    vil, conf = find_village(e["title"], e.get("village_db") or "")
    e["category"] = cat
    e["ambiguous"] = amb
    e["village"] = vil or ""
    e["village_confident"] = conf
    in_region = bool(vil) or bool(e.get("region_claim")) or ("بابلکنار" in (e["title"] or ""))
    if not in_region:
        around.append(e)               # خارج از ادعای منطقه‌ای → فایل اطراف
        continue
    (main if cat == "main" else other).append(e)

for lst in (main, other, around):
    lst.sort(key=lambda x: x["id"])

stats = {
    "union_total": len(union),
    "main_wooden": len(main),
    "other_villa_rustic": len(other),
    "around": len(around),
    "ambiguous_in_main": sum(1 for e in main if e["ambiguous"]),
    "village_uncertain_in_main": sum(1 for e in main if not e["village_confident"]),
    "by_source": {},
    "main_by_village": {},
}
for e in union.values():
    for s in e["sources"]:
        stats["by_source"][s] = stats["by_source"].get(s, 0) + 1
for e in main:
    v = e["village"] or "نامطمئن"
    stats["main_by_village"][v] = stats["main_by_village"].get(v, 0) + 1

with open(os.path.join(OUT_DIR, "roster.json"), "w", encoding="utf-8") as f:
    json.dump({"built_at": time.strftime("%Y-%m-%d %H:%M:%S"), "main": main, "other": other,
               "around": around, "stats": stats}, f, ensure_ascii=False, indent=1)

print(json.dumps(stats, ensure_ascii=False, indent=1))
