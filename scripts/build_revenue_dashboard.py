#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build revenue-dashboard.html from data/revenue/seydkola-mordad-1405.json
   + بخش realized از data/revenue/realized-seydkola-mordad-1405.json (اگر موجود باشد)
===========================================================================
  - تخمین درآمد (آینده): از API /api/nights — فقط شب‌های امروع به بعد
  - درآمد محقق‌شده (گذشته): از snapshotهای رادار — روزهای گذشته
"""
import json, os, html
from datetime import date

from radar_common import j_dm

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
SRC = os.path.join(ROOT, "data", "revenue", "seydkola-mordad-1405.json")
REALIZED_SRC = os.path.join(ROOT, "data", "revenue", "realized-seydkola-mordad-1405.json")
OUT = os.path.join(ROOT, "داشبورد-تخمین-درآمد.html")

# ===== 1. بارگذاری داده‌های تخمین (آینده / API) =====
data = json.load(open(SRC, encoding="utf-8"))
ok = [r for r in data if "error" not in r]
ok.sort(key=lambda r: r["net"], reverse=True)

pricing = json.load(open(os.path.join(ROOT, "data", "pricing", "pricing-dataset.json"), encoding="utf-8"))
host_by_id = {c["id"]: {"host_name": c.get("host_name", ""), "host_id": c.get("host_id")} for c in pricing}

def fa_digits_int(n):
    return f"{n:,}"

# ===== 2. ساخت ردیف‌های تخمین (API) =====
rows = []
for i, r in enumerate(ok, 1):
    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else ""
    nights_html = ""
    for n in sorted(r.get("nights", []), key=lambda x: x["date"]):
        g = n["date"]
        base = date(2026, 7, 23)
        gd_ = date.fromisoformat(g)
        delta = (gd_ - base).days
        if 0 <= delta < 31:
            jl = f"{delta+1} مرداد"
        elif 0 <= (gd_ - date(2026, 8, 23)).days < 31:
            jl = f"{(gd_ - date(2026, 8, 23)).days + 1} شهریور"
        else:
            jl = g
        flags = []
        if n.get("weekend"): flags.append("آخر هفته")
        if n.get("holiday"): flags.append("تعطیل")
        if n.get("peak"): flags.append("پیک")
        fl = (" <span class='flag'>" + "،".join(flags) + "</span>") if flags else ""
        disc = n.get("discount") or 0
        if disc:
            nights_html += f"<div class='nrow'><span class='nd'>{jl}</span><span class='np en'>{fa_digits_int(n['effective_price'])}</span><span class='old-price en'>{fa_digits_int(n['price'])}</span><span class='disc-badge'>{disc}٪ تخفیف</span>{fl}</div>"
        else:
            nights_html += f"<div class='nrow'><span class='nd'>{jl}</span><span class='np en'>{fa_digits_int(n['price'])}</span>{fl}</div>"
    host = host_by_id.get(r["id"], {"host_name": "", "host_id": None})
    rows.append({
        "rank": i, "medal": medal,
        "id": r["id"], "title": html.escape(r["title"]),
        "host_name": html.escape(host["host_name"] or "—"), "host_id": host["host_id"] or "",
        "booked": r["booked"], "free": r["free"],
        "gross": r.get("gross_discounted", r["gross"]), "discount": r.get("discount_total", 0),
        "commission": r["commission"], "net": r["net"],
        "nights_html": nights_html,
    })

tot_gross = sum(r.get("gross_discounted", r["gross"]) for r in ok)
tot_disc = sum(r.get("discount_total", 0) for r in ok)
tot_comm = sum(r["commission"] for r in ok)
tot_net = sum(r["net"] for r in ok)
tot_booked = sum(r["booked"] for r in ok)
n_booked = sum(1 for r in ok if r["booked"] > 0)

_all_dates = sorted(n["date"] for r in ok for n in r.get("nights", []))
range_label = f"{j_dm(_all_dates[0])} تا {j_dm(_all_dates[-1])} ۱۴۰۵" if _all_dates else "—"

# ===== 3. میزبان‌ها (تخمین API) =====
host_order = []
host_map = {}
for r in rows:
    key = str(r["host_id"]) if r["host_id"] else r["host_name"]
    if key not in host_map:
        host_map[key] = {
            "host_name": r["host_name"], "host_id": r["host_id"],
            "rooms_count": 0, "booked": 0, "gross": 0, "discount": 0,
            "commission": 0, "net": 0, "rooms_html": "",
        }
        host_order.append(key)
    h = host_map[key]
    h["rooms_count"] += 1
    h["booked"] += r["booked"]
    h["gross"] += r["gross"]
    h["discount"] += r["discount"]
    h["commission"] += r["commission"]
    h["net"] += r["net"]
    h["rooms_html"] += (f"<div class='nrow'><a class='title-link' href='https://www.jajiga.com/room/{r['id']}' "
                        f"target='_blank' rel='noopener'>{r['title']}</a> "
                        f"<span class='en' style='color:var(--muted);font-size:12px'>({r['id']})</span> "
                        f"<span class='en' style='color:var(--muted);font-size:12px'>{r['booked']} شب</span> "
                        f"<span class='en'>{fa_digits_int(r['gross'])}</span> "
                        f"<span class='en' style='color:#34d399;font-weight:700'>{fa_digits_int(r['net'])}</span></div>")

hosts = [host_map[k] for k in host_order]
hosts.sort(key=lambda h: h["net"], reverse=True)
for i, h in enumerate(hosts, 1):
    h["rank"] = i
    h["medal"] = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else ""

rows_json = json.dumps(rows, ensure_ascii=False)
hosts_json = json.dumps(hosts, ensure_ascii=False)

# ===== 4. بخش realized (روزهای گذشته از snapshotها) =====
realized_rooms = []
r_hosts = []
realized_kpi = {}
if os.path.exists(REALIZED_SRC):
    _r = json.load(open(REALIZED_SRC, encoding="utf-8"))
    _rr = _r.get("rooms") or []
    _rr.sort(key=lambda x: x.get("net", 0), reverse=True)
    _titles = {c["id"]: c.get("title", "") for c in pricing}
    for i, r in enumerate(_rr, 1):
        _nights_html = ""
        for n in sorted(r.get("nights", []), key=lambda x: x["date"]):
            _jl = j_dm(n["date"])
            _disc = n.get("discount") or 0
            _ep = n.get("effective_price") or n.get("price") or 0
            if _disc:
                _nights_html += (f"<div class='nrow'><span class='nd'>{html.escape(_jl)}</span>"
                                 f"<span class='np en'>{fa_digits_int(n['price'])}</span>"
                                 f"<span class='old-price en'>{fa_digits_int(_ep)}</span>"
                                 f"<span class='disc-badge'>{_disc}٪ تخفیف</span></div>")
            else:
                _nights_html += (f"<div class='nrow'><span class='nd'>{html.escape(_jl)}</span>"
                                 f"<span class='np en'>{fa_digits_int(_ep)}</span></div>")
        realized_rooms.append({
            "rank": i,
            "id": r.get("id"),
            "title": html.escape(_titles.get(r.get("id")) or r.get("title", "")),
            "host_name": html.escape(r.get("host_name", "")),
            "host_id": r.get("host_id", ""),
            "booked": r.get("booked", 0),
            "gross": r.get("gross_discounted", r.get("gross", 0)),
            "discount": r.get("discount_total", 0),
            "commission": r.get("commission", 0),
            "net": r.get("net", 0),
            "nights_html": _nights_html,
        })
    # میزبان‌ها (realized)
    _hmap, _forder = {}, []
    for r in realized_rooms:
        _key = str(r["host_id"]) if r["host_id"] else r["host_name"]
        if _key not in _hmap:
            _hmap[_key] = {"host_name": r["host_name"], "host_id": r["host_id"],
                           "rooms_count": 0, "booked": 0, "gross": 0, "discount": 0,
                           "commission": 0, "net": 0, "rooms_html": ""}
            _forder.append(_key)
        h = _hmap[_key]
        h["rooms_count"] += 1
        h["booked"] += r["booked"]
        h["gross"] += r["gross"]
        h["discount"] += r["discount"]
        h["commission"] += r["commission"]
        h["net"] += r["net"]
        h["rooms_html"] += (f"<div class='nrow'><a class='title-link' href='https://www.jajiga.com/room/{r['id']}' "
                            f"target='_blank' rel='noopener'>{r['title']}</a> "
                            f"<span class='en' style='color:var(--muted);font-size:11px'>({r['id']})</span> "
                            f"<span class='en' style='color:var(--muted);font-size:11px'>{r['booked']} شب</span> "
                            f"<span class='en'>{fa_digits_int(r['gross'] or 0)}</span> "
                            f"<span class='en' style='color:#34d399;font-weight:700'>{fa_digits_int(r['net'])}</span></div>")
    r_hosts = [_hmap[k] for k in _forder]
    r_hosts.sort(key=lambda h: h["net"], reverse=True)
    for i, h in enumerate(r_hosts, 1):
        h["rank"] = i
        h["medal"] = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else ""
    realized_kpi = {
        "n_rooms": len(realized_rooms),
        "n_booked": sum(1 for r in realized_rooms if r["booked"] > 0),
        "tot_booked": sum(r["booked"] for r in realized_rooms),
        "tot_gross": sum(r["gross"] for r in realized_rooms),
        "tot_disc": sum(r["discount"] for r in realized_rooms),
        "tot_comm": sum(r["commission"] for r in realized_rooms),
        "tot_net": sum(r["net"] for r in realized_rooms),
        "range": _r.get("realized_range") or "—",
    }

realized_json = json.dumps(realized_rooms, ensure_ascii=False)
rhosts_json = json.dumps(r_hosts, ensure_ascii=False)

# ===== 5. CSS =====
CSS = """
:root { --bg:#0b1526; --panel:#111d33; --panel2:#0e1930; --border:#1e2c47; --text:#e2e8f0;
        --muted:#8ea0bf; --accent:#3b82f6; --gold:#f59e0b; --silver:#94a3b8; --bronze:#b45309; }
* { margin:0; padding:0; box-sizing:border-box; }
body { background:var(--bg); color:var(--text); font-family:Vazirmatn, Tahoma, sans-serif; direction:rtl; }
.wrap { max-width:1200px; margin:0 auto; padding:24px 16px 60px; }
.hero { background:linear-gradient(135deg,#0e1c38 0%,#13294d 55%,#0e1c38 100%); border:1px solid var(--border);
        border-radius:16px; padding:26px 28px; margin-bottom:20px; box-shadow:0 10px 30px rgba(0,0,0,.35); }
.hero h1 { font-size:22px; font-weight:800; margin-bottom:6px; }
.hero .sub { color:var(--muted); font-size:13px; }
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin-bottom:22px; }
.card { background:var(--panel); border:1px solid var(--border); border-radius:12px; padding:14px 16px; }
.card .label { color:var(--muted); font-size:12px; margin-bottom:6px; }
.card .val { font-size:20px; font-weight:800; }
.card .val.gold { color:var(--gold); }
.card .val.green { color:#34d399; }
.rpanel { background:linear-gradient(135deg,#10223a 0%,#0b1526 100%); border:1px solid var(--border);
         border-radius:16px; padding:22px 24px; margin-bottom:22px; }
.rpanel h2 { font-size:16px; font-weight:800; margin-bottom:4px; color:#fbbf24; }
.rpanel .sub { color:var(--muted); font-size:12px; }
.rcard { background:var(--panel); border:1px solid var(--border); border-radius:12px; padding:14px 16px; }
.rcard .label { color:var(--muted); font-size:11px; margin-bottom:6px; }
.rcard .val { font-size:18px; font-weight:800; color:#fbbf24; }
.table-wrap { background:var(--panel); border:1px solid var(--border); border-radius:14px; overflow:auto; max-height:75vh;
        scrollbar-width:thin; scrollbar-color:#475569 #0b1526; scrollbar-gutter:stable; }
.table-wrap::-webkit-scrollbar { width:10px; height:10px; }
.table-wrap::-webkit-scrollbar-track { background:#0b1526; border-radius:8px; }
.table-wrap::-webkit-scrollbar-thumb { background:linear-gradient(180deg,#475569,#334155); border-radius:8px; border:2px solid #0b1526; }
.table-wrap::-webkit-scrollbar-thumb:hover { background:linear-gradient(180deg,#5b6f8f,#475569); }
.table-wrap::-webkit-scrollbar-corner { background:#0b1526; }
table { width:100%; border-collapse:collapse; min-width:820px; }
thead th { position:sticky; top:0; background:#13233f; color:#cbd5e1; font-size:12px; font-weight:700;
        padding:11px 10px; text-align:center; border-bottom:1px solid var(--border); cursor:pointer; user-select:none; white-space:nowrap; z-index:2; }
thead th .arrow { color:var(--accent); font-size:10px; margin-right:3px; }
tbody td { padding:10px 10px; text-align:center; border-bottom:1px solid #16233c; font-size:13px; }
tbody tr:hover { background:#15243f; }
tr.rank-1 { background:rgba(245,158,11,.07); }
tr.rank-2 { background:rgba(148,163,184,.07); }
tr.rank-3 { background:rgba(180,83,9,.07); }
td.title-cell { text-align:right; }
.title-link { color:var(--accent); text-decoration:none; font-weight:600; }
.title-link:hover { text-decoration:underline; }
.host-link { color:#f59e0b; text-decoration:none; font-weight:600; }
.host-link:hover { text-decoration:underline; }
.main-row { cursor:pointer; }
.en { font-family:'Courier New', Consolas, monospace; direction:ltr; unicode-bidi:embed; }
.medal { font-size:14px; }
.rank-num { color:var(--muted); font-weight:700; }
.detail-row td { background:var(--panel2); padding:10px 16px; }
.nrow { display:flex; gap:10px; align-items:center; padding:4px 0; border-bottom:1px dashed #1a2946; flex-wrap:wrap; }
.nrow:last-child { border-bottom:none; }
.nd { min-width:70px; color:var(--muted); font-size:12px; }
.np { color:#34d399; font-weight:700; }
.old-price { color:#64748b; text-decoration:line-through; font-size:11px; }
.disc-badge { background:#7f1d1d; color:#fca5a5; border-radius:6px; padding:1px 8px; font-size:11px; font-weight:700; }
.flag { background:#1f3a5f; color:#93c5fd; border-radius:6px; padding:1px 8px; font-size:11px; }
.empty { color:var(--muted); }
.section-title { font-size:17px; font-weight:800; margin:26px 0 10px; color:#e2e8f0; }
@media (max-width:640px){ .cards { grid-template-columns:repeat(2,1fr); } }
"""

# ===== 6. JS =====
JS = """
let sortKey = null, sortDir = -1;
const tbody = document.getElementById('tbody');
function fmt(n){ return n.toLocaleString('en-US'); }
function render(){
  let arr = DATA.slice();
  if (sortKey){
    arr.sort((a,b)=>{
      const av = sortValue(a), bv = sortValue(b);
      if (av === bv) return (b.net - a.net);
      if (typeof av === 'string') return sortDir * av.localeCompare(bv, 'fa');
      return sortDir * (av - bv);
    });
  }
  tbody.innerHTML = arr.map((r,i)=>{
    const rank = i+1;
    let medal = rank===1?'🥇':rank===2?'🥈':rank===3?'🥉':'';
    const hostCell = r.host_id
      ? `<a class="host-link" href="https://www.jajiga.com/user/${r.host_id}" target="_blank" rel="noopener">${r.host_name}</a>`
      : `<span style="color:var(--muted)">${r.host_name}</span>`;
    return `<tr class="main-row rank-${rank}" data-i="${i}">
      <td><span class="medal">${medal}</span> <span class="rank-num en">${rank}</span></td>
      <td class="title-cell"><a class="title-link" href="https://www.jajiga.com/room/${r.id}" target="_blank" rel="noopener">${r.title}</a> <span class="en" style="color:var(--muted);font-size:11px">(${r.id})</span></td>
      <td>${hostCell}</td>
      <td><span class="en">${r.booked}</span></td>
      <td><span class="en">${fmt(r.gross)}</span></td>
      <td>${r.discount ? '<span class="en" style="color:#f87171">'+fmt(r.discount)+'</span>' : '<span class="en" style="color:var(--muted)">0</span>'}</td>
      <td><span class="en">${fmt(r.commission)}</span></td>
      <td><span class="en" style="color:#34d399;font-weight:800">${fmt(r.net)}</span></td>
      <td><span class="chev" id="chev-${i}">▾</span></td>
    </tr>
    <tr class="detail-row" id="det-${i}" style="display:none">
      <td colspan="9"><b>شب‌های پر شده:</b> ${r.nights_html || '<span class="empty">رزروی ندارد</span>'}</td>
    </tr>`;
  }).join('');
  document.querySelectorAll('.main-row').forEach(tr=>{
    tr.onclick = (e)=>{
      if (e.target.closest('a')) return;
      const i = tr.dataset.i;
      const det = document.getElementById('det-'+i);
      const chev = document.getElementById('chev-'+i);
      const show = det.style.display==='none';
      det.style.display = show?'':'none';
      chev.textContent = show?'▴':'▾';
    };
  });
}
function sortValue(r){
  switch(sortKey){
    case 'rank': return r.net;
    case 'booked': return r.booked;
    case 'gross': return r.gross;
    case 'discount': return r.discount;
    case 'commission': return r.commission;
    case 'net': return r.net;
    case 'host': return r.host_name;
    default: return 0;
  }
}
document.querySelectorAll('th[data-key]').forEach(th=>{
  th.onclick = ()=>{
    const k = th.dataset.key;
    if (sortKey !== k){ sortKey = k; sortDir = -1; }
    else if (sortDir === -1){ sortDir = 1; }
    else { sortKey = null; sortDir = -1; }
    document.querySelectorAll('th .arrow').forEach(a=>a.textContent='');
    if (sortKey){ const a = th.querySelector('.arrow'); a.textContent = sortDir===-1?'▼':'▲'; }
    render();
  };
});
// ---- host aggregation table ----
let hostSortKey = null, hostSortDir = -1;
const hostTbody = document.getElementById('hostTbody');
function renderHosts(){
  let arr = HOSTS.slice();
  if (hostSortKey){
    arr.sort((a,b)=>{
      const av = hostSortValue(a), bv = hostSortValue(b);
      if (av === bv) return (b.net - a.net);
      if (typeof av === 'string') return hostSortDir * av.localeCompare(bv, 'fa');
      return hostSortDir * (av - bv);
    });
  }
  hostTbody.innerHTML = arr.map((h,i)=>{
    const rank = i+1;
    let medal = rank===1?'🥇':rank===2?'🥈':rank===3?'🥉':'';
    const hostCell = h.host_id
      ? `<a class="host-link" href="https://www.jajiga.com/user/${h.host_id}" target="_blank" rel="noopener">${h.host_name}</a>`
      : `<span style="color:var(--muted)">${h.host_name}</span>`;
    return `<tr class="host-row rank-${rank}" data-i="${i}">
      <td><span class="medal">${medal}</span> <span class="rank-num en">${rank}</span></td>
      <td>${hostCell}</td>
      <td><span class="en">${h.rooms_count}</span></td>
      <td><span class="en">${h.booked}</span></td>
      <td><span class="en">${fmt(h.gross)}</span></td>
      <td>${h.discount ? '<span class="en" style="color:#f87171">'+fmt(h.discount)+'</span>' : '<span class="en" style="color:var(--muted)">0</span>'}</td>
      <td><span class="en">${fmt(h.commission)}</span></td>
      <td><span class="en" style="color:#34d399;font-weight:800">${fmt(h.net)}</span></td>
      <td><span class="chev" id="hchev-${i}">▾</span></td>
    </tr>
    <tr class="detail-row" id="hdet-${i}" style="display:none">
      <td colspan="9"><b>اقامتگاه‌های این میزبان (ناخالص / خالص):</b> ${h.rooms_html || '<span class="empty">—</span>'}</td>
    </tr>`;
  }).join('');
  document.querySelectorAll('.host-row').forEach(tr=>{
    tr.onclick = (e)=>{
      if (e.target.closest('a')) return;
      const i = tr.dataset.i;
      const det = document.getElementById('hdet-'+i);
      const chev = document.getElementById('hchev-'+i);
      const show = det.style.display==='none';
      det.style.display = show?'':'none';
      chev.textContent = show?'▴':'▾';
    };
  });
}
function hostSortValue(h){
  switch(hostSortKey){
    case 'rank': return h.net;
    case 'rooms': return h.rooms_count;
    case 'booked': return h.booked;
    case 'gross': return h.gross;
    case 'discount': return h.discount;
    case 'commission': return h.commission;
    case 'net': return h.net;
    case 'host': return h.host_name;
    default: return 0;
  }
}
document.querySelectorAll('th[data-hkey]').forEach(th=>{
  th.onclick = ()=>{
    const k = th.dataset.hkey;
    if (hostSortKey !== k){ hostSortKey = k; hostSortDir = -1; }
    else if (hostSortDir === -1){ hostSortDir = 1; }
    else { hostSortKey = null; hostSortDir = -1; }
    document.querySelectorAll('th .arrow').forEach(a=>a.textContent='');
    if (hostSortKey){ const a = th.querySelector('.arrow'); a.textContent = hostSortDir===-1?'▼':'▲'; }
    renderHosts();
  };
});
render();
renderHosts();
"""

# فعال‌سازی بخش realized فقط اگر داده بارگذاری شده باشد
_RK_VARS = ""
_RK_BLOCK = ""
if realized_kpi:
    _RK_VARS = (
        f"const RK = {{ range:{json.dumps(realized_kpi.get('range','—'))}, "
        f"n_rooms:{realized_kpi.get('n_rooms',0)}, "
        f"n_booked:{realized_kpi.get('n_booked',0)}, "
        f"tot_booked:{realized_kpi.get('tot_booked',0)}, "
        f"tot_gross:{realized_kpi.get('tot_gross',0)}, "
        f"tot_disc:{realized_kpi.get('tot_disc',0)}, "
        f"tot_comm:{realized_kpi.get('tot_comm',0)}, "
        f"tot_net:{realized_kpi.get('tot_net',0)} }};"
    )
    _RK_BLOCK = (
        f'  <div class="rpanel">\n'
        f'    <h2>✅ درآمد محقق‌شده (روزهای گذشته)</h2>\n'
        f'    <div class="sub">بازه: {html.escape(realized_kpi.get("range","—"))} '
        f'&nbsp;•&nbsp; محاسبه از snapshotهای روزانه رادار '
        f'&nbsp;•&nbsp; {realized_kpi.get("n_rooms","—")} کلبه با رزرو</div>\n'
        f'  </div>\n'
        f'  <div class="cards">\n'
        f'    <div class="rcard"><div class="label">کلبه‌های دارای رزرو (گذشته)</div>'
        f'<div class="val en">{realized_kpi.get("n_booked","—")} / {realized_kpi.get("n_rooms","—")}</div></div>\n'
        f'    <div class="rcard"><div class="label">کل شب‌های پر (گذشته)</div>'
        f'<div class="val en">{realized_kpi.get("tot_booked","—")}</div></div>\n'
        f'    <div class="rcard"><div class="label">جمع تخفیف (گذشته)</div>'
        f'<div class="val en" style="color:#f87171">{realized_kpi.get("tot_disc",0):,}</div></div>\n'
        f'    <div class="rcard"><div class="label">ناخالص (گذشته)</div>'
        f'<div class="val en">{realized_kpi.get("tot_gross",0):,}</div></div>\n'
        f'    <div class="rcard"><div class="label">کمیسیون ۱۲٪ (گذشته)</div>'
        f'<div class="val en" style="color:#f87171">{realized_kpi.get("tot_comm",0):,}</div></div>\n'
        f'    <div class="rcard"><div class="label">درآمد خالص (گذشته)</div>'
        f'<div class="val en" style="color:#34d399">{realized_kpi.get("tot_net",0):,}</div></div>\n'
        f'  </div>\n'
    )

# JS اضافی برای جداول realized
if realized_kpi:
    JS += """
// ---- realized tables ----
const rtbody = document.getElementById('rtbody');
let rsortKey = null, rsortDir = -1;
function renderRealized(){
  if (!REALIZED.length){ document.getElementById('rcards').innerHTML = '<span class="empty" style="color:var(--muted);padding:10px">داده‌ای موجود نیست</span>'; return; }
  let arr = REALIZED.slice();
  if (rsortKey){
    arr.sort((a,b)=>{
      const av = rsortValue(a), bv = rsortValue(b);
      if (av === bv) return (b.net - a.net);
      if (typeof av === 'string') return rsortDir * av.localeCompare(bv, 'fa');
      return rsortDir * (av - bv);
    });
  }
  rtbody.innerHTML = arr.map((r,i)=>{
    const rank = i+1;
    let medal = rank===1?'🥇':rank===2?'🥈':rank===3?'🥉':'';
    const hostCell = r.host_id
      ? `<a class="host-link" href="https://www.jajiga.com/user/${r.host_id}" target="_blank" rel="noopener">${r.host_name}</a>`
      : `<span style="color:var(--muted)">${r.host_name}</span>`;
    return `<tr class="main-row rank-${rank}" data-i="${i}" data-t="r">
      <td><span class="medal">${medal}</span> <span class="rank-num en">${rank}</span></td>
      <td class="title-cell"><a class="title-link" href="https://www.jajiga.com/room/${r.id}" target="_blank" rel="noopener">${r.title}</a> <span class="en" style="color:var(--muted);font-size:11px">(${r.id})</span></td>
      <td>${hostCell}</td>
      <td><span class="en">${r.booked}</span></td>
      <td><span class="en">${fmt(r.gross)}</span></td>
      <td>${r.discount ? '<span class="en" style="color:#f87171">'+fmt(r.discount)+'</span>' : '<span class="en" style="color:var(--muted)">0</span>'}</td>
      <td><span class="en">${fmt(r.commission)}</span></td>
      <td><span class="en" style="color:#34d399;font-weight:800">${fmt(r.net)}</span></td>
      <td><span class="chev" id="rchev-${i}">▾</span></td>
    </tr>
    <tr class="detail-row" id="rdet-${i}" style="display:none">
      <td colspan="9"><b>شب‌های پر شده:</b> ${r.nights_html || '<span class="empty">رزروی ندارد</span>'}</td>
    </tr>`;
  }).join('');
  document.querySelectorAll('.main-row[data-t="r"]').forEach(tr=>{
    tr.onclick = (e)=>{
      if (e.target.closest('a')) return;
      const i = tr.dataset.i;
      const det = document.getElementById('rdet-'+i);
      const chev = document.getElementById('rchev-'+i);
      const show = det.style.display==='none';
      det.style.display = show?'':'none';
      chev.textContent = show?'▴':'▾';
    };
  });
}
function rsortValue(r){
  switch(rsortKey){
    case 'rank': return r.net;
    case 'booked': return r.booked;
    case 'gross': return r.gross;
    case 'discount': return r.discount;
    case 'commission': return r.commission;
    case 'net': return r.net;
    case 'host': return r.host_name;
    default: return 0;
  }
}
document.querySelectorAll('th[data-rkey]').forEach(th=>{
  th.onclick = ()=>{
    const k = th.dataset.rkey;
    if (rsortKey !== k){ rsortKey = k; rsortDir = -1; }
    else if (rsortDir === -1){ rsortDir = 1; }
    else { rsortKey = null; rsortDir = -1; }
    document.querySelectorAll('th .arrow').forEach(a=>a.textContent='');
    if (rsortKey){ const a = th.querySelector('.arrow'); a.textContent = rsortDir===-1?'▼':'▲'; }
    renderRealized();
  };
});
// ---- realized host table ----
const rhostTbody = document.getElementById('rhostTbody');
let rhsortKey = null, rhsortDir = -1;
function renderRhosts(){
  if (!RHOSTS.length){ return; }
  let arr = RHOSTS.slice();
  if (rhsortKey){
    arr.sort((a,b)=>{
      const av = rhSortValue(a), bv = rhSortValue(b);
      if (av === bv) return (b.net - a.net);
      if (typeof av === 'string') return rhsortDir * av.localeCompare(bv, 'fa');
      return rhsortDir * (av - bv);
    });
  }
  rhostTbody.innerHTML = arr.map((h,i)=>{
    const rank = i+1;
    let medal = rank===1?'🥇':rank===2?'🥈':rank===3?'🥉':'';
    const hostCell = h.host_id
      ? `<a class="host-link" href="https://www.jajiga.com/user/${h.host_id}" target="_blank" rel="noopener">${h.host_name}</a>`
      : `<span style="color:var(--muted)">${h.host_name}</span>`;
    return `<tr class="host-row rank-${rank}" data-i="${i}" data-t="rh">
      <td><span class="medal">${medal}</span> <span class="rank-num en">${rank}</span></td>
      <td>${hostCell}</td>
      <td><span class="en">${h.rooms_count}</span></td>
      <td><span class="en">${h.booked}</span></td>
      <td><span class="en">${fmt(h.gross)}</span></td>
      <td>${h.discount ? '<span class="en" style="color:#f87171">'+fmt(h.discount)+'</span>' : '<span class="en" style="color:var(--muted)">0</span>'}</td>
      <td><span class="en">${fmt(h.commission)}</span></td>
      <td><span class="en" style="color:#34d399;font-weight:800">${fmt(h.net)}</span></td>
      <td><span class="chev" id="rhchev-${i}">▾</span></td>
    </tr>
    <tr class="detail-row" id="rhdet-${i}" style="display:none">
      <td colspan="9"><b>اقامتگاه‌های این میزبان:</b> ${h.rooms_html || '<span class="empty">—</span>'}</td>
    </tr>`;
  }).join('');
  document.querySelectorAll('.host-row[data-t="rh"]').forEach(tr=>{
    tr.onclick = (e)=>{
      if (e.target.closest('a')) return;
      const i = tr.dataset.i;
      const det = document.getElementById('rhdet-'+i);
      const chev = document.getElementById('rhchev-'+i);
      const show = det.style.display==='none';
      det.style.display = show?'':'none';
      chev.textContent = show?'▴':'▾';
    };
  });
}
function rhSortValue(h){
  switch(rhsortKey){
    case 'rank': return h.net;
    case 'rooms': return h.rooms_count;
    case 'booked': return h.booked;
    case 'gross': return h.gross;
    case 'discount': return h.discount;
    case 'commission': return h.commission;
    case 'net': return h.net;
    case 'host': return h.host_name;
    default: return 0;
  }
}
document.querySelectorAll('th[data-rhkey]').forEach(th=>{
  th.onclick = ()=>{
    const k = th.dataset.rhkey;
    if (rhsortKey !== k){ rhsortKey = k; rhsortDir = -1; }
    else if (rhsortDir === -1){ rhsortDir = 1; }
    else { rhsortKey = null; rhsortDir = -1; }
    document.querySelectorAll('th .arrow').forEach(a=>a.textContent='');
    if (rhsortKey){ const a = th.querySelector('.arrow'); a.textContent = rhsortDir===-1?'▼':'▲'; }
    renderRhosts();
  };
});
renderRealized();
renderRhosts();
"""

# ===== 7. HTML نهایی =====
html_out = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>درآمد تخمینی کلبه‌های سیدکلا — تا ۳۱ مرداد ۱۴۰۵</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <div class="hero">
    <h1>📊 درآمد تخمینی کلبه‌های سیدکلا</h1>
    <div class="sub">بازه: {range_label} &nbsp;•&nbsp; {len(ok)} کلبه &nbsp;•&nbsp; کمیسیون ۱۲٪ &nbsp;•&nbsp; با احتساب تخفیف هر شب &nbsp;•&nbsp; منبع: API تقویم جاجیگا</div>
  </div>

{_RK_BLOCK}

  <div class="cards">
    <div class="card"><div class="label">کلبه‌های دارای رزرو</div><div class="val en">{n_booked} / {len(ok)}</div></div>
    <div class="card"><div class="label">کل شب‌های پر</div><div class="val en">{tot_booked}</div></div>
    <div class="card"><div class="label">جمع تخفیف</div><div class="val en" style="color:#f87171">{tot_disc:,}</div></div>
    <div class="card"><div class="label">ناخالص (با تخفیف)</div><div class="val en">{tot_gross:,}</div></div>
    <div class="card"><div class="label">کمیسیون ۱۲٪</div><div class="val en" style="color:#f87171">{tot_comm:,}</div></div>
    <div class="card"><div class="label">درآمد خالص</div><div class="val green en">{tot_net:,}</div></div>
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th data-key="rank">رتبه <span class="arrow"></span></th>
          <th>عنوان</th>
          <th data-key="host">نام میزبان <span class="arrow"></span></th>
          <th data-key="booked">شب‌های پر <span class="arrow"></span></th>
          <th data-key="gross">ناخالص (تومان) <span class="arrow"></span></th>
          <th data-key="discount">تخفیف (تومان) <span class="arrow"></span></th>
          <th data-key="commission">کمیسیون (تومان) <span class="arrow"></span></th>
          <th data-key="net">خالص (تومان) <span class="arrow"></span></th>
          <th>جزئیات</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>

  <h2 class="section-title">🏠 درآمد هر میزبان (جمع همه اقامتگاه‌ها)</h2>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th data-hkey="rank">رتبه <span class="arrow"></span></th>
          <th data-hkey="host">نام میزبان <span class="arrow"></span></th>
          <th data-hkey="rooms">تعداد اقامتگاه <span class="arrow"></span></th>
          <th data-hkey="booked">شب‌های پر <span class="arrow"></span></th>
          <th data-hkey="gross">ناخالص (تومان) <span class="arrow"></span></th>
          <th data-hkey="discount">تخفیف (تومان) <span class="arrow"></span></th>
          <th data-hkey="commission">کمیسیون (تومان) <span class="arrow"></span></th>
          <th data-hkey="net">خالص (تومان) <span class="arrow"></span></th>
          <th>جزئیات</th>
        </tr>
      </thead>
      <tbody id="hostTbody"></tbody>
    </table>
  </div>

"""

# بخش realized در جیمل خروجی (اگر داده داشته باشد)
if realized_kpi:
    html_out += _RK_BLOCK  # KPIهای realized (rpanel + rcardها)
    html_out += """  <h2 class="section-title">✅ درآمد محقق‌شده (روزهای گذشته)</h2>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th data-rkey="rank">رتبه <span class="arrow"></span></th>
          <th>عنوان</th>
          <th data-rkey="host">نام میزبان <span class="arrow"></span></th>
          <th data-rkey="booked">شب‌های پر <span class="arrow"></span></th>
          <th data-rkey="gross">ناخالص (تومان) <span class="arrow"></span></th>
          <th data-rkey="discount">تخفیف (تومان) <span class="arrow"></span></th>
          <th data-rkey="commission">کمیسیون (تومان) <span class="arrow"></span></th>
          <th data-rkey="net">خالص (تومان) <span class="arrow"></span></th>
          <th>جزئیات</th>
        </tr>
      </thead>
      <tbody id="rtbody"></tbody>
    </table>
  </div>

  <h2 class="section-title">🏠 درآمد هر میزبان (گذشته)</h2>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th data-rhkey="rank">رتبه <span class="arrow"></span></th>
          <th data-rhkey="host">نام میزبان <span class="arrow"></span></th>
          <th data-rhkey="rooms">تعداد اقامتگاه <span class="arrow"></span></th>
          <th data-rhkey="booked">شب‌های پر <span class="arrow"></span></th>
          <th data-rhkey="gross">ناخالص (تومان) <span class="arrow"></span></th>
          <th data-rhkey="discount">تخفیف (تومان) <span class="arrow"></span></th>
          <th data-rhkey="commission">کمیسیون (تومان) <span class="arrow"></span></th>
          <th data-rhkey="net">خالص (تومان) <span class="arrow"></span></th>
          <th>جزئیات</th>
        </tr>
      </thead>
      <tbody id="rhostTbody"></tbody>
    </table>
  </div>
</div>
"""
else:
    html_out += "</div>\n"

html_out += f"""</body>
<script>
const DATA = {rows_json};
const HOSTS = {hosts_json};
const REALIZED = {realized_json};
const RHOSTS = {rhosts_json};
{_RK_VARS}
{JS}
</script>
</html>
"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(html_out)
print(f"Saved: {OUT} | {len(ok)} rooms | realized: {len(realized_rooms)} rooms")
