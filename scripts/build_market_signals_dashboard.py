#!/usr/bin/env python3
"""build_market_signals_dashboard.py — single-file RTL dashboard for 5 market signals.

Tabs: رتبه جستجو | تقویم پریمیوم | تخفیف و تغییر قیمت | ROI امکانات | اثر بج‌ها
Data: data/signals/{rank_history.json, signals_computed.json} + radar-config labels.
All Jalali conversion done in Python (jdatetime); JS only renders.
"""
import json
from datetime import date

import jdatetime

BASE = import_path = __import__("pathlib").Path(__file__).resolve().parent.parent
SIG = BASE / "data" / "signals"
OUT = BASE / "market-signals-dashboard.html"


JMONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
           "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
JWD = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]


def to_jalali(iso):
    y, m, d = (int(x) for x in iso.split("-"))
    j = jdatetime.date.fromgregorian(date=date(y, m, d))
    return {"y": j.year, "m": j.month, "d": j.day,
            "mfa": JMONTHS[j.month - 1], "jwd": JWD[j.weekday()]}


def main():
    hist = json.load(open(SIG / "rank_history.json", encoding="utf-8"))
    sig = json.load(open(SIG / "signals_computed.json", encoding="utf-8"))
    cfg = json.load(open(BASE / "data" / "radar" / "radar-config.json", encoding="utf-8"))
    labels = {str(r["id"]): {"label": r["label"], "short": r["short_label"], "own": r.get("own", False)}
              for r in cfg["rooms"]}

    # pre-convert dates for rank history + premium calendar
    jdays = {day: {rid: v for rid, v in d.items()} for day, d in hist.items()}

    # premium calendar: convert keys, weekday already gregorian — recompute via jalali weekday
    prem = {}
    for iso, row in sig["holiday_premium"].items():
        j = to_jalali(iso)
        prem[iso] = {**row, "j": j, "wk_fa": row["is_weekend"]}

    # repricing events: convert date/snapshot
    evs = []
    for e in sig["repricing_events_tail"]:
        e2 = {**e, "j_date": to_jalali(e["date"]), "j_snap": to_jalali(e["snapshot"])}
        evs.append(e2)

    payload = {
        "labels": labels,
        "rank_days": [{"iso": k, "j": to_jalali(k), "v": v} for k, v in sorted(hist.items())],
        "premium": [{"iso": k, **v} for k, v in sorted(prem.items())],
        "repricing": evs,
        "repricing_total": sig["repricing_events_total"],
        "discounts": sig["discount_census"],
        "amenities": sig["amenity_roi"],
        "badges": sig["badge_effect"],
        "generated": to_jalali(sig["generated"]),
        "nsnaps": len(sig["snapshots_used"]),
    }
    html = TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False))
    OUT.write_text(html, encoding="utf-8")
    print(f"written {OUT.name} ({OUT.stat().st_size/1024:.0f} KB)")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="fa" dir="rtl"><head><meta charset="UTF-8">
<title>سیگنال‌های بازار جاجیگا — بابلکنار</title>
<style>
:root{--bg:#0d1117;--card:#161b22;--border:#30363d;--text:#e6edf3;--muted:#8b949e;--accent:#58a6ff;--green:#3fb950;--red:#f85149;--gold:#e3b341;--purple:#a371f7}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:Vazirmatn,'Segoe UI',Tahoma,sans-serif;direction:rtl}
.en{font-family:Consolas,monospace;direction:ltr;unicode-bidi:embed;display:inline-block}
.wrap{max-width:1250px;margin:0 auto;padding:16px}
h1{font-size:20px;margin-bottom:2px}.sub{color:var(--muted);font-size:12px;margin-bottom:14px}
.tabs{display:flex;gap:6px;margin-bottom:14px;flex-wrap:wrap;position:sticky;top:0;background:var(--bg);z-index:9;padding:6px 0}
.tab{background:var(--card);border:1px solid var(--border);color:var(--muted);padding:8px 16px;border-radius:8px;cursor:pointer;font-size:13px;transition:.15s}
.tab:hover{color:var(--text)}
.tab.on{background:#1f6feb33;color:var(--accent);border-color:var(--accent)}
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px;margin-bottom:14px}
h2{font-size:15px;margin-bottom:10px;color:var(--accent)}
h2 .cnt{color:var(--muted);font-size:11px;font-weight:400;margin-inline-start:6px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{position:sticky;top:0;background:#1c2128;color:var(--muted);padding:7px 6px;border-bottom:1px solid var(--border);text-align:center;font-size:11.5px;z-index:2}
td{padding:5px 6px;border-bottom:1px solid #21262d;text-align:center}
td.r{text-align:right}
tr:hover td{background:#1c212855}
.m1{color:var(--gold)}.m2{color:#c9d1d9}.m3{color:#c98850}
.own td{background:#1f6feb14!important}.own td:first-child{border-right:2px solid var(--accent)}
.up{color:var(--red)}.down{color:var(--green)}.flat{color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(128px,1fr));gap:7px}
.cell{background:#1c2128;border-radius:8px;padding:7px 5px;text-align:center;border:1px solid var(--border)}
.cell.fri,.cell.sat{border-color:var(--purple);background:#1c2128}
.cell .d{font-size:11px;color:var(--muted)}
.cell .v{font-size:15px;font-weight:700;margin:3px 0}
.hot{color:var(--red)}.warm{color:var(--gold)}.cool{color:var(--green)}
.cell .n{font-size:9.5px;color:var(--muted)}
.stat{display:inline-block;background:#1c2128;border:1px solid var(--border);border-radius:8px;padding:7px 14px;margin:3px;text-align:center;min-width:105px}
.stat .v{font-size:17px;font-weight:700;color:var(--accent)}
.stat .l{font-size:10.5px;color:var(--muted)}
.stat.g .v{color:var(--green)}.stat.r .v{color:var(--red)}.stat.y .v{color:var(--gold)}
.barwrap{background:#0d1117;border-radius:4px;height:14px;position:relative;overflow:hidden;min-width:70px}
.bar{position:absolute;top:0;bottom:0;border-radius:4px}
.bar.p{background:#f8514955;right:50%}
.bar.n{background:#3fb95055;left:50%;right:auto}
.note{color:var(--muted);font-size:11px;margin-top:8px;line-height:1.9}
.legend{display:flex;gap:14px;font-size:11px;color:var(--muted);margin-bottom:8px;flex-wrap:wrap}
.legend b{font-weight:400}.lg-up{color:var(--red)}.lg-dn{color:var(--green)}
</style></head><body><div class="wrap" id="app"></div>
<script>
const D = __DATA__;
const F = n => n==null?'—':Number(n).toLocaleString('en-US');
const P = v => v==null?'—':(v>0?'+':'')+v+'٪';
const app = document.getElementById('app');
let html = `<h1>سیگنال‌های بازار — بابلکنار</h1>
<div class="sub">تولید ${D.generated.jd} ${D.generated.mfa} ${D.generated.y} · منبع: ${D.nsnaps} اسنپ‌شات رادار + سرشماری ${D.discounts.rooms} اتاق فعال</div>`;
const tabs=[['rank','جستجو'],['prem','تقویم پریمیوم'],['repr','تخفیف/قیمت'],['roi','ROI امکانات'],['badge','اثر بج‌ها']];
html+=`<div class="tabs">`+tabs.map((t,i)=>`<div class="tab ${i===0?'on':''}" data-t="${t[0]}">${t[1]}</div>`).join('')+`</div>`;

/* ---------- tab 1: ranks ---------- */
const lastDay = D.rank_days[D.rank_days.length-1];
const rooms = Object.keys(lastDay.v).filter(k=>k[0]!=='_');
html+=`<div class="tabpane" data-p="rank">
<div class="card"><h2>رتبه در جستجوی جاجیگا <span class="cnt">آخرین اسکن: ${lastDay.j.jd} ${lastDay.j.mfa}</span></h2>
<div>`+ lastDay && Object.entries(lastDay.v._villages||{}).map(([v,s])=>`<span class="stat"><span class="v en">${s.seen}/${s.total}</span><span class="l">${v}</span></span>`).join('') +`</div>
<table><thead><tr><th>#</th><th>اتاق</th><th>سیدکلا (از 34)</th><th>کل بابلکنار (از 442)</th></tr></thead><tbody>`;
rooms.filter(id=>true).forEach(id=>{
  const me=lastDay.v[id], L=D.labels[id]||{short:id,own:false};
  const own=L.own?'own':''; const medal=r=>r===1?'m1':r===2?'m2':r===3?'m3':'';
  if(!me) return;
  const sk=me.villages['سیدکلا'], bk=me.villages['بابلکنار (کل)'];
  html+=`<tr class="${own}"><td class="en ${medal(sk||bk)}">${sk||bk}</td><td class="r">${L.short}</td>
  <td class="en ${medal(sk||'')}">${sk??'—'}</td><td class="en ${medal(bk||'')}">${bk??'—'}</td></tr>`;
});
html+=`</tbody></table><div class="note">رتبه = جایگاه در ترتیب نمایش API جستجو. اولین خوانش با مرورگر وریفای شد (سیدمهدی ۱، خودت ۲ در سیدکلا یعنی صفحه اول نتایج). اتاق‌های بدون رتبه در هیچ صفحهای پیدا نشدن.</div></div></div>`;

/* ---------- tab 2: premium calendar ---------- */
html+=`<div class="tabpane" data-p="prem" style="display:none">
<div class="card"><h2>پریمیوم قیمت رقبا به تفکیک شب <span class="cnt">میانگین تغییر قیمت هر شب نسبت به میانگین روزهای غیرآخرهفته همان اتاق</span></h2>
<div class="legend"><b>مرزی بنفش = جمعه/شنبه</b><b class="lg-up">قرمز: گران‌تر از عادی (پریمیوم)</b><b class="lg-dn">سبز: همسان یا ارزان‌تر</b></div><div class="grid">`;
D.premium.forEach(r=>{
  const v=r.median_premium;
  const cls=v>=60?'hot':v>=20?'warm':v<=0?'cool':'';
  const clsCell=r.is_weekend?(r.j.wd==='جمعه'?'fri':'sat'):'';
  html+=`<div class="cell ${clsCell}"><div class="d">${r.j.jd} ${r.j.mfa} · ${r.j.wd}</div>
  <div class="v ${cls} en">${P(v)}</div><div class="n">${r.n_rooms} اتاق</div></div>`;
});
html+=`</div><div class="note">راهنمای قیمت‌گذاری: برای هر تاریخ شکارشده، پریمیوم میانه رقبا تقریبا همان عددیه که بازار حاضر پرداختن. مثلا جایی که میانه ١٠٠٪ روی قیمت عادیه، یعنی رقبا همونجا دوبرابر گرفتن.</div></div></div>`;

/* ---------- tab 3: discount/repricing ---------- */
html+=`<div class="tabpane" data-p="repr" style="display:none">
<div class="card"><h2>سرشماری تخفیف بازار <span class="cnt">${D.discounts.rooms} اتاق فعال</span></h2>
<div><span class="stat"><span class="v en">${D.discounts.current_active}</span><span class="l">تخفیف دوره‌ای فعال الان</span></span>`+
Object.entries(D.discounts.by_type).map(([t,n])=>`<span class="stat ${t==='duration'?'y':'g'}"><span class="v en">${n}</span><span class="l">${t}</span></span>`).join('')+`</div>
<h2 style="margin-top:12px">ساختار تخفیف مدت‌دار (top)</h2>
<table><thead><tr><th>نوع</th><th>درصد</th><th>حداقل شب</th><th>تعداد اتاق</th></tr></thead><tbody>`;
Object.entries(D.discounts.values).forEach(([k,n])=>{
  const [t,p,mn]=k.split('/');
  html+=`<tr><td>${t==='duration'?'مدت‌دار':t==='today_discount'?'امروز':t==='tomorrow_discount'?'فردا':t}</td><td class="en">${p}٪</td><td class="en">${mn==='Nonen'?'—':mn}</td><td class="en">${n}</td></tr>`;
});
html+=`</tbody></table></div>
<div class="card"><h2>تغییرات قیمت رقبا (بین دو اسنپ‌شات) <span class="cnt">مجموع ${D.repricing_total} رویداد · نمایش آخرین ${D.repricing.length}</span></h2>
<table><thead><tr><th>اسنپ‌شات</th><th>شب</th><th>اتاق</th><th>قبلی</th><th>جدید</th><th>تغییر</th></tr></thead><tbody>`;
D.repricing.slice().reverse().slice(0,80).forEach(e=>{
  html+=`<tr><td class="en">${e.j_snap.jd} ${e.j_snap.mfa}</td><td class="en">${e.j_date.jd} ${e.j_date.mfa}</td>
  <td class="r">${e.room}</td><td class="en">${F(e.old)}</td><td class="en">${F(e.new)}</td>
  <td class="en ${e.change_pct>0?'up':e.change_pct<0?'down':'flat'}">${P(e.change_pct)}</td></tr>`;
});
html+=`</tbody></table></div></div>`;

/* ---------- tab 4: amenity ROI ---------- */
html+=`<div class="tabpane" data-p="roi" style="display:none">
<div class="card"><h2>ROI امکانات <span class="cnt">مد قیمت گروه با مد قیمت کل بازار (${F(D.amenities.base_median_price)}) سنجیده می‌شود</span></h2>
<table><thead><tr><th>امکانات</th><th>تعداد اتاق</th><th>مد قیمت</th><th>پریمیوم نسبت به بازار</th><th>میانگین رزرو موفق</th><th>رزرو نسبت به بازار</th></tr></thead><tbody>`;
const FA={jacuzzi:'جکوزی',pool:'استخر',billiard:'بیلیارد',foosball:'فوتبال دستی',washer:'ماشین لباسشویی',microwave:'مایکروویو',wifi:'وای‌فای',elevator:'آسانسور',drawer:'کابینت/دراور',toilet:'توالت فرنگی',tv:'تلویزیون',barbecue:'باربیکیو',furniture:'مبلمان',kitchen:'آشپزخانه',_all:'کل بازار'};
D.amenities.rows.filter(r=>r.feature!=='_all'&&['jacuzzi','pool','billiard','foosball','washer','microwave','wifi','elevator','drawer','toilet','tv','barbecue','furniture','kitchen'].includes(r.feature))
.sort((a,b)=>b.price_premium_pct-a.price_premium_pct).forEach(r=>{
  const pp=r.price_premium_pct, bp=r.books_vs_market_pct;
  const w=Math.min(Math.abs(pp),150)/(150*2)*100;
  html+=`<tr><td class="r">${FA[r.feature]||r.feature}</td><td class="en">${r.n}</td><td class="en">${F(r.median_price)}</td>
  <td><div class="barwrap"><div class="bar ${pp>=0?'p':'n'}" style="width:${w}%;${pp<0?'right:0;':''}"></div><span class="en ${pp>=0?'up':'down'}" style="font-size:11px">${P(pp)}</span></div></td>
  <td class="en">${r.avg_books}</td><td class="en ${bp>=0?'up':'down'}">${P(bp)}</td></tr>`;
});
html+=`</tbody></table><div class="note">مقادیر بالا یعنی: جکوزی +۳۳٪ قیمت و +۴۵٪ رزرو؛ استخر +۱۰۷٪ قیمت؛ ولی امکانات گران مثل بیلیارد/مایکروویو قیمت رو بالا میبرن ولی رزرو میانگین رو نمیارن (نمونه‌ها کمه، با احتیاط بردار).</div></div></div>`;

/* ---------- tab 5: badges ---------- */
html+=`<div class="tabpane" data-p="badge" style="display:none">
<div class="card"><h2>اثر برچسب‌ها روی رزرو موفق <span class="cnt">دسته‌بندی ${462} اتاق فعال</span></h2>
<table><thead><tr><th>ترکیب بج</th><th>تعداد</th><th>مد رزرو موفق</th><th>میانگین رزرو</th><th>مد قیمت</th></tr></thead><tbody>`;
Object.entries(D.badges).forEach(([k,v])=>{
  html+=`<tr><td class="r">${k}</td><td class="en">${v.n}</td><td class="en ${v.median_books>=50?'up':''}">${F(v.median_books)}</td>
  <td class="en">${v.avg_books}</td><td class="en">${F(v.median_price)}</td></tr>`;
});
html+=`</tbody></table><div class="note">بدون بج فوری/پلاس: نرخ شاگرد ۴-هات خیلی کمتره — بدون بج مد رزرو ۴، فقط پلاس ۲۰، فوری+پلاس ۵۰. یعنی فعال‌کردن رزرو فوری اگر شرایطش رو داری، چندبرابر تخفیف اثر داره.</div></div></div>`;

app.innerHTML=html;
document.querySelectorAll('.tab').forEach(t=>t.addEventListener('click',()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
  document.querySelectorAll('.tabpane').forEach(x=>x.style.display='none');
  t.classList.add('on');
  document.querySelector(`.tabpane[data-p="${t.dataset.t}"]`).style.display='block';
}));
</script></body></html>
"""

if __name__ == "__main__":
    main()
