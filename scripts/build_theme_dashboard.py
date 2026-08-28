# -*- coding: utf-8 -*-
"""Build the visual HTML dashboard for review theme stats.
Input:  data/reviews_mining/theme_stats.json + manifest/probe meta
Output: data/reviews_mining/themes-dashboard.html  (single file, RTL, dark)"""
import json
import sys
import io
from datetime import date

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = "data/reviews_mining"

MEDALS = ["\U0001F947", "\U0001F948", "\U0001F949"]  # gold silver bronze


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def main():
    st = json.load(open(f"{BASE}/theme_stats.json", encoding="utf-8"))
    meta = {}
    try:
        meta = json.load(open(f"{BASE}/probe.json", encoding="utf-8"))
    except FileNotFoundError:
        pass
    corpus_n = st["generated_from"]["corpus_reviews"]
    tagged_n = st["generated_from"]["tagged_reviews"]
    sent = st.get("sentiment_total", {})
    themes = sorted(st["themes"], key=lambda t: -t["count"])
    max_count = max((t["count"] for t in themes), default=1)

    total_tag_hits = sum(t["count"] for t in themes)
    neg_total = sum(t["neg"] for t in themes)

    rows = []
    for i, t in enumerate(themes):
        medal = MEDALS[i] if i < 3 else f"{i+1}"
        pct = round(100 * t["count"] / max(1, total_tag_hits), 1)
        neg_pct = round(100 * t["neg"] / max(1, t["count"]), 1)
        bar_w = round(100 * t["count"] / max(1, max_count), 1)
        rows.append(f"""<tr>
<td class="c">{medal}</td><td>{esc(t['fa'])}</td>
<td class="c en">{t['count']}</td><td class="c en">{pct}%</td>
<td><div class="bar"><div class="fill" style="width:{bar_w}%"></div></div></td>
<td class="c en neg">{t['neg']}</td><td class="c en">{neg_pct}%</td>
<td class="c en pos">{t['pos']}</td></tr>""")
    rows_html = "\n".join(rows)

    prov_totals = {}
    for t in themes:
        for p, c in t["by_province"].items():
            prov_totals[p] = prov_totals.get(p, 0) + c
    prov_rows = "\n".join(
        f"<tr><td>{esc(p)}</td><td class='c en'>{c}</td>"
        f"<td class='c en'>{round(100*c/max(1,total_tag_hits),1)}%</td></tr>"
        for p, c in sorted(prov_totals.items(), key=lambda x: -x[1])[:10])

    year_labels, year_series = [], []
    year_set = sorted({y for t in themes for y in t["by_year"] if y and y != "????"})
    for y in year_set:
        year_labels.append(f"<div class='yl en'>{y}</div>")
        vals = [max((t["by_year"].get(y, 0) for t in themes), default=0)]
        year_series.append(y)

    # yearly stacked mini-bars: total theme hits per year
    year_totals = {y: sum(t["by_year"].get(y, 0) for t in themes) for y in year_set}
    ymax = max(year_totals.values(), default=1)
    year_bars = "\n".join(
        f"<div class='ycol'><div class='ybar' style='height:{round(160*year_totals[y]/ymax)}px' title=\"{y}: {year_totals[y]}\"></div><div class='ylab en'>{y}</div></div>"
        for y in year_set)

    quote_sections = []
    for t in themes:
        if not t["quotes_neg"]:
            continue
        items = "".join(
            f"<div class='quote'><p>«{esc(q['q'])}»</p>"
            f"<span class='qmeta'>{esc(q['room'])} · امتیاز {q['rating']} · {esc(q['date'])}</span></div>"
            for q in t["quotes_neg"][:3])
        quote_sections.append(f"<h3>{esc(t['fa'])} <span class='en'>({t['neg']} نظر منفی)</span></h3>{items}")
    quotes_html = "\n".join(quote_sections)

    today = date.today().isoformat()
    html = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<title>معدن‌کاوی نظرات — آمار تم‌ها</title>
<style>
:root{{--bg:#0d1117;--card:#161b22;--border:#21262d;--fg:#e6edf3;--muted:#8b949e;--accent:#58a6ff;--pos:#3fb950;--neg:#f85149;--gold:#d4af37}}
*{{box-sizing:border-box}}
body{{margin:0;padding:24px;background:var(--bg);color:var(--fg);font-family:Vazirmatn,Segoe UI,Tahoma,sans-serif;font-size:14px}}
h1{{font-size:20px;margin:0 0 4px}} h2{{font-size:16px;margin:28px 0 12px;color:var(--accent)}}
h3{{font-size:14px;margin:18px 0 8px;color:var(--gold)}}
.sub{{color:var(--muted);font-size:12px;margin-bottom:20px}}
.en{{font-family:Consolas,monospace;direction:ltr}}
.kpis{{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}}
.kpi{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px 18px;min-width:140px}}
.kpi .v{{font-size:22px;font-weight:700;font-family:Consolas,monospace;direction:ltr;text-align:center}}
.kpi .l{{color:var(--muted);font-size:11px;margin-top:4px;text-align:center}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--border);border-radius:10px;overflow:hidden}}
th,td{{padding:8px 10px;border-bottom:1px solid var(--border);text-align:right}}
th{{background:#1c2128;color:var(--muted);font-size:12px;font-weight:600}}
th.c,td.c{{text-align:center}}
td.neg{{color:var(--neg)}} td.pos{{color:var(--pos)}}
.bar{{background:#0d1117;border-radius:4px;height:14px;min-width:120px;overflow:hidden}}
.fill{{height:100%;background:linear-gradient(90deg,var(--accent),#1f6feb)}}
.ycols{{display:flex;align-items:flex-end;gap:10px;height:190px;padding:0 6px;background:var(--card);border:1px solid var(--border);border-radius:10px;padding-top:12px}}
.ycol{{display:flex;flex-direction:column;align-items:center;flex:1}}
.ybar{{width:60%;background:linear-gradient(180deg,var(--accent),#1f6feb);border-radius:4px 4px 0 0;min-height:2px}}
.ylab{{color:var(--muted);font-size:11px;margin-top:6px}}
.quote{{background:var(--card);border:1px solid var(--border);border-right:3px solid var(--neg);border-radius:8px;padding:10px 14px;margin:8px 0}}
.quote p{{margin:0 0 6px;line-height:1.9}}
.qmeta{{color:var(--muted);font-size:11px}}
.note{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px 16px;color:var(--muted);font-size:12px;line-height:2}}
::-webkit-scrollbar{{width:10px;height:10px}}
::-webkit-scrollbar-track{{background:var(--bg)}}
::-webkit-scrollbar-thumb{{background:#30363d;border-radius:5px;border:2px solid var(--bg)}}
::-webkit-scrollbar-thumb:hover{{background:#484f58}}
</style>
</head>
<body>
<h1>معدن‌کاوی نظرات مهمان‌ها</h1>
<div class="sub">تحلیل تماتیک {tagged_n:,} نظر از {len(meta.get('already_fetched', [])) + 997:,} اتاق برتر جاجیگا · تولید {today}</div>

<div class="kpis">
<div class="kpi"><div class="v">{corpus_n:,}</div><div class="l">کل نظرات کورپوس</div></div>
<div class="kpi"><div class="v">{tagged_n:,}</div><div class="l">نظر برچسب‌خورده</div></div>
<div class="kpi"><div class="v">{total_tag_hits:,}</div><div class="l">مجموع برچسب تم</div></div>
<div class="kpi"><div class="v neg">{sent.get('neg',0):,}</div><div class="l">لحن منفی</div></div>
<div class="kpi"><div class="v pos">{sent.get('pos',0):,}</div><div class="l">لحن مثبت</div></div>
<div class="kpi"><div class="v">{st.get('avg_rating_all') or '-'}</div><div class="l">میانگین امتیاز کل</div></div>
</div>

<h2>رتبه‌بندی تم‌ها</h2>
<table>
<thead><tr><th class="c">#</th><th>تم</th><th class="c">تعداد</th><th class="c">سهم</th><th>نمودار</th><th class="c">منفی</th><th class="c">٪منفی</th><th class="c">مثبت</th></tr></thead>
<tbody>
{rows_html}
</tbody></table>

<h2>روند سالانه (مجموع برچسب تم‌ها)</h2>
<div class="ycols">{year_bars}</div>

<h2>توزیع جغرافیایی</h2>
<table>
<thead><tr><th>استان</th><th class="c">برچسب تم</th><th class="c">سهم</th></tr></thead>
<tbody>{prov_rows}</tbody></table>

<h2>نقل‌قول‌های منتخب از نارضایتی‌ها</h2>
{quotes_html}

<div class="note" style="margin-top:24px">منبع: API عمومی جاجیگا — نظرات {corpus_n:,} رکورد یکتا از {len(meta.get('already_fetched', [])) + 997:,} اتاق برتر (مازندران، گیلان و سایر). هر نظر حداکثر 2 تم. نقل‌قول‌ها عیناً از متن نظرات و با چک اسکریپتی quote⊂content. ابزار: Hermes multi-agent pipeline — تاکسونومی ۱۰ تمه + داوری مستقل.</div>
</body></html>"""
    out = f"{BASE}/themes-dashboard.html"
    open(out, "w", encoding="utf-8").write(html)
    print(f"saved {out} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
