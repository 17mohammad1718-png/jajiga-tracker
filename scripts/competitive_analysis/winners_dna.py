#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""winners_dna.py — تسک ۳: DNA موفق‌ترین‌ها + آپ‌لیفت امکانات + اثر روستا + باند قیمت منصفانه
خروجی: analysis/winners_dna.md (گزارش خام برای REPORT) + چاپ خلاصه
"""
import json
import os
from collections import Counter

ROOT = r"H:/projects/jajiga-tracker"
ANA = os.path.join(ROOT, "exports", "competitive_2026-09-08", "analysis")
OWN_ID = "3297585"

rows = json.load(open(os.path.join(ANA, "analysis_rooms.json"), encoding="utf-8"))
own = next(r for r in rows if r["شناسه"] == OWN_ID)
main = [r for r in rows if r["دسته"] == "main" and r["شناسه"] != OWN_ID]

def med(vals):
    v = sorted(x for x in vals if x is not None)
    if not v:
        return None
    n = len(v)
    return round(v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2, 1)

def pctile(vals, p):
    v = sorted(x for x in vals if x is not None)
    if not v:
        return None
    i = max(0, min(len(v) - 1, round((len(v) - 1) * p / 100)))
    return v[i]

out_lines = []

def w(s=""):
    out_lines.append(s)
    print(s)

def fmt_tom(v):
    if v is None:
        return "—"
    return f"{round(v):,}"

# ============ بخش ۱: دو رتبه‌بندی برنده ============
w("## بخش ۱: دو رتبه‌بندی برنده‌ها")
w()

top_raw = sorted([r for r in main if r.get("success_books") is not None],
                 key=lambda r: -r["success_books"])[:20]
# نرمال‌شده: فقط با عمر >= 3 ماه (جلوگیری از نویز آگهی تازه)
top_norm = sorted([r for r in main if r.get("کتاب_بر_ماه") is not None and (r.get("عمر_ماه") or 0) >= 3],
                  key=lambda r: -r["کتاب_بر_ماه"])[:20]

def profile(group):
    n = len(group)
    return {
        "n": n,
        "جکوزی٪": round(sum(r["جکوزی"] for r in group) * 100 / n),
        "استخر٪": round(sum(r["استخر"] for r in group) * 100 / n),
        "دربست٪": round(sum(r["دربست"] for r in group) * 100 / n),
        "پلاس٪": round(sum(r["پلاس"] for r in group) * 100 / n),
        "فوری٪": round(sum(r["رزرو_فوری"] for r in group) * 100 / n),
        "میانه_متراژ": med([r["متراژ_بنا"] for r in group]),
        "میانه_ظرفیت": med([r["ظرفیت_پایه"] for r in group]),
        "میانه_قیمت_آخرهفته": med([r.get("قیمت_دوشب_آخر_هفته") for r in group]),
        "میانه_امتیاز": med([r.get("امتیاز_کلی") for r in group]),
        "میانه_عمر_ماه": med([r.get("عمر_ماه") for r in group]),
        "روستاها": Counter(r["روستا"] for r in group).most_common(5),
    }

w("### ۱-الف: Top-20 با رزرو انباشته خام (success_books)")
p = profile(top_raw)
for k, v in p.items():
    w(f"- {k}: {v}")
w()
w("اتاق‌ها (id | نام کوتاه | books | قیمت آخرهفته | روستا):")
for r in top_raw[:12]:
    t = r["عنوان"][:28]
    w(f"- {r['شناسه']} | {t} | {r['success_books']} | {fmt_tom(r.get('قیمت_دوشب_آخر_هفته'))} | {r['روستا']}")
w()

w("### ۱-ب: Top-20 با رزرو نرمال‌شده (کتاب/ماه، عمر≥3 ماه)")
p = profile(top_norm)
for k, v in p.items():
    w(f"- {k}: {v}")
w()
w("اتاق‌ها (id | نام کوتاه | کتاب/ماه | books | عمرماه | قیمت آخرهفته | روستا):")
for r in top_norm[:12]:
    t = r["عنوان"][:28]
    w(f"- {r['شناسه']} | {t} | {r['کتاب_بر_ماه']} | {r['success_books']} | {r['عمر_ماه']} | {fmt_tom(r.get('قیمت_دوشب_آخر_هفته'))} | {r['روستا']}")
w()

# ============ بخش ۲: آپ‌لیفت امکانات ============
w("## بخش ۲: آپ‌لیفت هر امکان (میانه، روی کلبه‌های قیمت‌دار main)")
priced = [r for r in main if r.get("قیمت_دوشب_آخر_هفته") is not None]
w(f"n کلبه‌های قیمت‌دار: {len(priced)} از {len(main)}")
w()
w("| امکان | n دارد | میانه قیمت دارد | میانه بدون | آپ‌لیفت قیمت | میانه کتاب/ماه دارد | بدون |")
w("|---|---|---|---|---|---|---|")

def uplift_line(key, label, pool):
    has = [r for r in pool if r[key] == 1 and r.get("قیمت_دوشب_آخر_هفته")]
    hasnt = [r for r in pool if r[key] == 0 and r.get("قیمت_دوشب_آخر_هفته")]
    if len(has) < 10 or len(hasnt) < 10:
        return f"| {label} | {len(has)} | — | — | n کوچک | — | — |"
    ph, pn = med([r["قیمت_دوشب_آخر_هفته"] for r in has]), med([r["قیمت_دوشب_آخر_هفته"] for r in hasnt])
    bh = med([r.get("کتاب_بر_ماه") for r in has])
    bn = med([r.get("کتاب_بر_ماه") for r in hasnt])
    lift = round((ph - pn) * 100 / pn) if pn else None
    return f"| {label} | {len(has)} | {fmt_tom(ph)} | {fmt_tom(pn)} | {lift:+d}٪ | {bh} | {bn} |"

for key, label in [("جکوزی", "جکوزی"), ("استخر", "استخر"), ("حیاط_محصور", "حیاط محصور"),
                   ("ویو_جنگل", "چشم‌انداز جنگل"), ("دربست", "دربست (بدون هم‌سایه)"),
                   ("پلاس", "اقامتگاه پلاس"), ("رزرو_فوری", "رزرو فوری")]:
    w(uplift_line(key, label, priced))
w()

# متراژ به باند
w("### قیمت بر حسب باند متراژ (main قیمت‌دار)")
w("| باند متراژ | n | میانه قیمت آخرهفته | میانه کتاب/ماه |")
w("|---|---|---|---|")
for lo, hi in [(0, 60), (60, 90), (90, 130), (130, 10**9)]:
    g = [r for r in priced if r.get("متراژ_بنا") and lo <= r["متراژ_بنا"] < hi]
    if len(g) < 8:
        w(f"| {lo}–{hi if hi < 10**8 else '+'} | {len(g)} | n کوچک | n کوچک |")
        continue
    lab = f"{lo}–{hi}" if hi < 10**8 else f"{lo}+"
    w(f"| {lab} | {len(g)} | {fmt_tom(med([r['قیمت_دوشب_آخر_هفته'] for r in g]))} | {med([r.get('کتاب_بر_ماه') for r in g])} |")
w()

# ============ بخش ۳: اثر روستا ============
w("## بخش ۳: اثر روستا (فقط روستای مطمئن، n≥8)")
w("| روستا | n | میانه قیمت آخرهفته | میانه کتاب/ماه | جکوزی٪ |")
w("|---|---|---|---|---|")
villages = {}
for r in main:
    if r["روستا_مطمئن"] and r.get("قیمت_دوشب_آخر_هفته"):
        villages.setdefault(r["روستا"], []).append(r)
for v, g in sorted(villages.items(), key=lambda kv: -med([x.get("کتاب_بر_ماه") for x in kv[1]] or [0])):
    if len(g) < 8:
        continue
    w(f"| {v} | {len(g)} | {fmt_tom(med([r['قیمت_دوشب_آخر_هفته'] for r in g]))} | "
      f"{med([r.get('کتاب_بر_ماه') for r in g])} | {round(sum(r['جکوزی'] for r in g)*100/len(g))}٪ |")
w()

# ============ بخش ۴: باند قیمت منصفانه کلبه من ============
w("## بخش ۴: باند قیمت منصفانه کلبه 3297585")
# مشابه‌ها: سیدکلا OR متراژ 70-130 با ظرفیت پایه 4-5
comps = [r for r in main
         if (r["روستا"] == "سیدکلا" and r["روستا_مطمئن"])
         or (r.get("متراژ_بنا") and 70 <= r["متراژ_بنا"] <= 130 and r.get("ظرفیت_پایه") in (4, 5))]
comps = [r for r in comps if r.get("قیمت_دوشب_آخر_هفته") is not None and r["شناسه"] != OWN_ID]
prices = sorted(r["قیمت_دوشب_آخر_هفته"] for r in comps)
p25, p75 = pctile(prices, 25), pctile(prices, 75)
mine = own["قیمت_دوشب_آخر_هفته"]
w(f"n مشابه‌ها (سیدکلا یا متراژ70-130 و ظرفیت 4-5، قیمت‌دار): {len(comps)}")
w(f"P25 = {fmt_tom(p25)} | میانه = {fmt_tom(med(prices))} | P75 = {fmt_tom(p75)}")
w(f"قیمت فعلی من (آخرهفته دو شب): {fmt_tom(mine)}")
if p25 and mine:
    pos = "زیر باند" if mine < p25 else ("درون باند" if mine <= p75 else "بالاتر از باند")
    w(f"→ موقعیت: **{pos}** ({round((mine-p25)*100/p25):+d}٪ نسبت به P25)")
w()
w("قیمت‌های مشابه‌ها (مرتب):")
for r in sorted(comps, key=lambda r: r["قیمت_دوشب_آخر_هفته"]):
    star = " ← من" if False else ""
    w(f"- {r['شناسه']} | {r['عنوان'][:34]} | {r['روستا']} | {r['متراژ_بنا']}م | "
      f"جکوزی:{'بله' if r['جکوزی'] else '-'} | {fmt_tom(r['قیمت_دوشب_آخر_هفته'])}")

with open(os.path.join(ANA, "winners_dna.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(out_lines))
print("\n[saved] winners_dna.md")
