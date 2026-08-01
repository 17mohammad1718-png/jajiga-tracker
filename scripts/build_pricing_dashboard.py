"""Build pricing-dashboard.html from data/pricing/pricing-dataset.json.

Phase 1 dashboard — DATA VIEW ONLY (no analysis/algorithm yet).
Reads the merged factor dataset and injects it into a self-contained
RTL Persian single-file HTML dashboard.
"""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "pricing", "pricing-dataset.json")
OUT = os.path.join(ROOT, "pricing-dashboard.html")

with open(DATA, encoding="utf-8") as f:
    data = json.load(f)

# village order for the filter chips + stats
VILLAGE_ORDER = ["سیدکلا", "گونه کلا", "قرآن تالار", "شیردارکلا"]

FEATURE_ICONS = {
    "pool": "🏊", "swimmingpool": "🏊", "jacuzzi": "🛁", "wifi": "📶",
    "parking": "🅿️", "tv": "📺", "kitchen": "🍳", "refrigerator": "🧊",
    "barbecue": "🍢", "washer": "🧺", "hairdryer": "💨", "janitor": "🛡️",
    "heating": "🔥", "cooler": "❄️", "stave": "🍳", "table": "🪑",
    "furniture": "🛋️", "bathroom": "🚿", "islamictoilet": "🚽", "toilet": "🚽",
    "essentials": "🧻", "electricity": "⚡", "water": "💧", "fireextingu": "🧯",
    "firstaidkit": "🩹", "firealarm": "🚨", "safetycard": "📋",
    "vacuumcleaner": "🧹", "food": "🍲", "drawer": "🗄️", "fridge": "🧊",
}

# Persian names for feature keys that have no description in the API
FEATURE_FA = {
    "essentials": "ملزومات اولیه", "electricity": "برق", "water": "آب لوله‌کشی",
    "heating": "گرمایش", "cooler": "سرمایش", "stave": "اجاق گاز",
    "refrigerator": "یخچال", "refrigeratorfreezer": "یخچال فریزر",
    "parking": "پارکینگ", "islamictoilet": "سرویس ایرانی", "bathroom": "حمام",
    "barbecue": "باربیکیو", "kitchen": "آشپزخانه", "tv": "تلویزیون",
    "furniture": "مبلمان", "janitor": "نگهبان", "jacuzzi": "جکوزی",
    "pool": "استخر", "swimmingpool": "استخر", "fireextingu": "کپسول آتش‌نشانی",
    "table": "میز", "drawer": "کشو", "firstaidkit": "جعبه کمک‌های اولیه",
    "safetycard": "برگه ایمنی", "vacuumcleaner": "جاروبرقی", "toilet": "سرویس بهداشتی",
    "wifi": "وای‌فای", "washer": "ماشین لباسشویی", "food": "سرو غذا",
    "hairdryer": "سشوار", "firealarm": "آژیر آتش", "fridge": "یخچال",
}

PROPERTY_EMOJI = {
    "خوش منظره": "🏔️", "مهمان نواز": "🤝", "جذاب": "✨", "اقامتگاه خاص": "💎",
    "خوش غذا": "🍽️", "حیاط دار": "🌳", "لب آب": "💦", "استخر آب گرم": "♨️",
    "استخر سرپوشیده": "🏊",
}

CANCEL_LABEL = {"middle": "میانه", "hard": "سخت", "flexible": "آسان"}

HTML = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>کلبه‌های بابلکنار — داده قیمت‌گذاری</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;600;800&display=swap" rel="stylesheet">
<style>
:root {
  --bg:#0d1117; --card:#161b22; --card2:#1b212c; --border:#262d3a;
  --text:#e6edf3; --muted:#8b949e; --accent:#58a6ff; --gold:#d4a72c;
  --green:#3fb950; --yellow:#d29922; --red:#f85149; --purple:#bc8cff;
  --pink:#f778ba;
}
* { box-sizing:border-box; margin:0; padding:0; }
body { background:var(--bg); color:var(--text); font-family:'Vazirmatn',Tahoma,sans-serif; padding-bottom:60px; }
.en { font-family:Consolas,'Courier New',monospace; direction:ltr; unicode-bidi:embed; font-variant-numeric:tabular-nums; }

.hero { background:linear-gradient(135deg,#10263f 0%,#0d1117 60%); border-bottom:1px solid var(--border); padding:26px 20px 20px; }
.hero h1 { font-size:24px; font-weight:800; }
.hero .sub { color:var(--muted); margin-top:6px; font-size:13px; }
.chips { display:flex; gap:8px; margin-top:12px; flex-wrap:wrap; }
.chip { background:rgba(88,166,255,.12); border:1px solid rgba(88,166,255,.3); color:var(--accent); border-radius:999px; padding:3px 12px; font-size:12px; }

.stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:10px; padding:16px 20px; }
.stat { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:12px 14px; }
.stat .k { font-size:12px; color:var(--muted); }
.stat .v { font-size:20px; font-weight:800; margin-top:4px; }
.stat .v small { font-size:11px; color:var(--muted); font-weight:400; }

.toolbar { display:flex; gap:10px; padding:0 20px 14px; flex-wrap:wrap; align-items:center; }
.village-filters { display:flex; gap:6px; flex-wrap:wrap; }
.vf-btn { background:var(--card); border:1px solid var(--border); color:var(--muted); border-radius:999px; padding:5px 14px; font-size:12px; cursor:pointer; font-family:inherit; transition:all .15s; }
.vf-btn:hover { border-color:var(--accent); color:var(--text); }
.vf-btn.active { background:var(--accent); border-color:var(--accent); color:#0d1117; font-weight:600; }
.vf-btn .cnt { font-family:Consolas,monospace; font-size:10.5px; opacity:.75; margin-inline-start:4px; }
.search-box { flex:1; min-width:220px; background:var(--card); border:1px solid var(--border); color:var(--text); border-radius:10px; padding:9px 14px; font-family:inherit; font-size:13px; }
.search-box:focus { outline:none; border-color:var(--accent); }
.hint { color:var(--muted); font-size:11px; }

.table-wrap { padding:0 20px; overflow-x:auto; }
table { width:100%; border-collapse:collapse; background:var(--card); border-radius:12px; overflow:hidden; }
thead th { background:var(--card2); padding:10px 8px; font-size:12px; color:var(--muted); cursor:pointer; user-select:none; white-space:nowrap; text-align:center; border-bottom:1px solid var(--border); position:sticky; top:0; }
thead th:hover { color:var(--text); }
thead th .arrow { font-size:10px; margin-inline-start:3px; color:var(--accent); }
tbody td { padding:9px 8px; font-size:12.5px; text-align:center; border-bottom:1px solid #20262f; white-space:nowrap; }
tbody tr.data-row { cursor:pointer; transition:background .15s; }
tbody tr.data-row:hover { background:#1c232e; }
tbody tr.data-row.own-row { background:rgba(212,167,44,.07); }
tbody tr.data-row.own-row:hover { background:rgba(212,167,44,.13); }
td.title { text-align:right; max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.title-link { color:var(--accent); text-decoration:none; }
.title-link:hover { text-decoration:underline; }
.host-link { color:#e8934a; text-decoration:none; }
.host-link:hover { text-decoration:underline; }
.own-badge { display:inline-block; background:var(--gold); color:#111; font-size:10px; font-weight:800; border-radius:4px; padding:1px 6px; margin-inline-start:6px; vertical-align:middle; }
.badge { display:inline-block; background:rgba(139,148,158,.15); border:1px solid rgba(139,148,158,.3); color:var(--muted); border-radius:6px; padding:1px 6px; font-size:10.5px; margin:1px; }
.badge.scenic { background:rgba(63,185,80,.12); border-color:rgba(63,185,80,.35); color:var(--green); }
.village-tag { display:inline-block; background:rgba(88,166,255,.1); border:1px solid rgba(88,166,255,.28); color:var(--accent); border-radius:6px; padding:1px 7px; font-size:10.5px; white-space:nowrap; }
.badge.plus { background:rgba(212,167,44,.12); border-color:rgba(212,167,44,.4); color:var(--gold); }
.badge.instant { background:rgba(88,166,255,.12); border-color:rgba(88,166,255,.35); color:var(--accent); }
.occ { font-weight:700; }
.occ-ok { color:var(--green); } .occ-mid { color:var(--yellow); } .occ-hot { color:var(--red); }
.rating-hi { color:var(--green); } .rating-mid { color:var(--yellow); }
.disc { color:var(--green); font-weight:700; }

tbody tr.detail-row > td { padding:0; background:var(--card); }
.detail-inner { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:14px; padding:16px 18px; text-align:right; }
.detail-block { background:var(--card2); border:1px solid var(--border); border-radius:10px; padding:12px; min-width:0; overflow:hidden; }
.detail-block h4 { font-size:12px; color:var(--muted); margin-bottom:8px; font-weight:600; }
.detail-block h4::after { content:''; display:block; width:34px; height:2px; background:var(--accent); margin-top:4px; border-radius:2px; }
.feat-line { font-size:12px; padding:2px 0; border-bottom:1px dashed #20262f; overflow-wrap:anywhere; }
.feat-line:last-child { border-bottom:none; }
.feat-line .fname { font-weight:600; }
.feat-line .fdesc { color:var(--muted); font-weight:400; }
.subrating { display:flex; justify-content:space-between; font-size:12px; padding:3px 0; border-bottom:1px dashed #20262f; }
.subrating:last-child { border-bottom:none; }
.subrating .lbl { color:var(--muted); }
.host-line { font-size:12px; padding:3px 0; color:var(--text); }
.host-line .lbl { color:var(--muted); }
.link { color:var(--accent); text-decoration:none; font-size:12px; }
.link:hover { text-decoration:underline; }

footer { text-align:center; color:var(--muted); font-size:11px; padding:24px 20px 10px; }
@media (max-width:700px){ .stats{grid-template-columns:repeat(2,1fr);} }
</style>
</head>
<body>
<div class="hero">
  <h1>🏡 کلبه‌های بابلکنار — داده قیمت‌گذاری</h1>
  <div class="sub">فاز ۱: جمع‌آوری داده (بدون تحلیل) — پایه الگوریتم قیمت‌گذاری. منبع: api.jajiga.com/api/room</div>
  <div class="chips" id="heroChips"></div>
</div>

<div class="stats" id="statsRow"></div>

<div class="toolbar">
  <div class="village-filters" id="villageFilters"></div>
  <input class="search-box" id="searchBox" placeholder="جستجو در عنوان یا میزبان...">
  <span class="hint">برای مرتب‌سازی روی ستون کلیک کنید (▼ زیاد → ▲ کم → بدون مرتب‌سازی). روی ردیف کلیک کنید تا جزئیات کامل باز شود.</span>
</div>

<div class="table-wrap">
  <table>
    <thead>
      <tr id="headRow"></tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>
</div>

<footer>فاز ۱ — فقط نمایش داده. تحلیل و ساخت الگوریتم قیمت‌گذاری مرحله به مرحله با نظارت شما انجام می‌شود.</footer>

<script type="application/json" id="pricingData">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('pricingData').textContent);
const FEATURE_FA = __FEATURE_FA__;
const PROP_EMOJI = __PROP_EMOJI__;
const CANCEL = __CANCEL__;

const en = n => (n === null || n === undefined) ? '—' : Number(n).toLocaleString('en-US');
const pct = (a, b) => b ? Math.round(a / b * 100) : 0;

function occClass(o) {
  if (o === null || o === undefined) return '';
  if (o <= 5) return 'occ-ok';
  if (o <= 15) return 'occ-mid';
  return 'occ-hot';
}

const SORT_COLS = [
  { key:'rank', label:'#', val:c=>c.min_price||0 },
  { key:'title', label:'عنوان', val:c=>c.title||'' },
  { key:'village', label:'روستا', val:c=>c.village||'' },
  { key:'host', label:'میزبان', val:c=>c.host_name||'' },
  { key:'price', label:'قیمت', val:c=>c.min_price||0 },
  { key:'area', label:'متراژ', val:c=>c.floor_area||0 },
  { key:'land', label:'زمین', val:c=>c.land_area||0 },
  { key:'bed', label:'اتاق', val:c=>c.bedrooms||0 },
  { key:'guest', label:'ظرفیت', val:c=>c.max_guest_number||0 },
  { key:'feats', label:'امکانات', val:c=>c.features_count||0 },
  { key:'props', label:'برچسب‌ها', val:c=>(c.properties||[]).length },
  { key:'rating', label:'امتیاز', val:c=>c.rating||0 },
  { key:'reviews', label:'نظرات', val:c=>c.reviews||0 },
  { key:'books', label:'تعداد رزرو', val:c=>c.success_books||0 },
  { key:'occ', label:'اشغال', val:c=>c.occupancy_30||0 },
  { key:'disc', label:'تخفیف', val:c=>c.current_discount_percent||0 },
];

let sortKey = null, sortDir = -1;
let activeVillage = null;   // null = all villages
let tbody, headRow, statsRow, searchBox, villageFilters, heroChips;

// Gregorian -> Jalali (month names included)
const JM = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];
function g2j(gy, gm, gd) {
  const gdm = [0,31,59,90,120,151,181,212,243,273,304,334];
  const gy2 = gm > 2 ? gy + 1 : gy;
  let d = 355666 + 365*gy + ~~((gy2+3)/4) - ~~((gy2+99)/100) + ~~((gy2+399)/400) + gd + gdm[gm-1];
  let jy = -1595 + 33 * ~~(d/12053); d %= 12053;
  jy += 4 * ~~(d/1461); d %= 1461;
  if (d > 365) { jy += ~~((d-1)/365); d = (d-1) % 365; }
  let jm, jd;
  if (d < 186) { jm = 1 + ~~(d/31); jd = 1 + (d%31); }
  else { jm = 7 + ~~((d-186)/30); jd = 1 + ((d-186)%30); }
  return [jy, jm, jd];
}
function toJalali(dateStr) {
  if (!dateStr) return null;
  const [y,m,d] = dateStr.split('-').map(Number);
  const [jy,jm,jd] = g2j(y,m,d);
  return `از ${JM[jm-1]} ${jy}`;
}

function defaultOrder() { return [...DATA].sort((a,b)=>(a.min_price||0)-(b.min_price||0)); }

function getFiltered() {
  const q = (searchBox.value||'').trim().toLowerCase();
  let arr = DATA;
  if (activeVillage) arr = arr.filter(c => c.village === activeVillage);
  if (!q) return arr;
  return arr.filter(c =>
    (c.title||'').toLowerCase().includes(q) || (c.host_name||'').toLowerCase().includes(q) ||
    (c.properties||[]).join(' ').toLowerCase().includes(q) ||
    (c.features||[]).join(' ').toLowerCase().includes(q));
}

function getSorted() {
  const arr = getFiltered();
  if (!sortKey) return arr.sort((a,b)=>(a.min_price||0)-(b.min_price||0));
  const col = SORT_COLS.find(c=>c.key===sortKey);
  const dir = sortDir;
  return arr.sort((a,b)=>{
    let va = col.val(a), vb = col.val(b);
    if (va === vb) return ((a.min_price||0)-(b.min_price||0)) || ((a.success_books||0)-(b.success_books||0));
    if (typeof va === 'string' || typeof vb === 'string') return String(va).localeCompare(String(vb), 'fa') * dir;
    return (va - vb) * dir;
  });
}

function renderStats() {
  const n = DATA.length;
  const prices = DATA.map(c=>c.min_price||0).sort((a,b)=>a-b);
  const avg = Math.round(prices.reduce((s,p)=>s+p,0)/n);
  const pools = DATA.filter(c=>c.pool).length;
  const jacs = DATA.filter(c=>c.jacuzzi).length;
  const scenic = DATA.filter(c=>(c.properties||[]).includes('خوش منظره')).length;
  const books = DATA.reduce((s,c)=>s+(c.success_books||0),0);
  const reviews = DATA.reduce((s,c)=>s+(c.reviews||0),0);
  const items = [
    {k:'کلبه‌ها', v:en(n)},
    {k:'میانگین قیمت', v:en(avg), s:'ت/شب'},
    {k:'بازه قیمت', v:en(prices[0])+' تا '+en(prices[n-1]), s:'هزار'},
    {k:'استخردار', v:en(pools)},
    {k:'جکوزی', v:en(jacs)},
    {k:'خوش‌منظره', v:en(scenic)},
    {k:'رزرو موفق کل', v:en(books)},
    {k:'نظرات کل', v:en(reviews)},
  ];
  statsRow.innerHTML = items.map(s=>`<div class="stat"><div class="k">${s.k}</div><div class="v">${s.v}${s.s?`<small> ${s.s}</small>`:''}</div></div>`).join('');
}

function renderVillageFilters() {
  const counts = {};
  DATA.forEach(c => { counts[c.village] = (counts[c.village]||0) + 1; });
  const order = ['همه', ...Object.keys(counts)];
  villageFilters.innerHTML = order.map(v => {
    const key = v === 'همه' ? null : v;
    const cnt = v === 'همه' ? DATA.length : counts[v];
    const active = activeVillage === key ? 'active' : '';
    return `<button class="vf-btn ${active}" data-v="${key||'__all__'}">${v}<span class="cnt">${en(cnt)}</span></button>`;
  }).join('');
  villageFilters.querySelectorAll('.vf-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      activeVillage = btn.dataset.v === '__all__' ? null : btn.dataset.v;
      renderVillageFilters();
      renderStats();
      renderTable();
    });
  });
}

function renderHeroChips() {
  const n = DATA.length;
  const villages = [...new Set(DATA.map(c=>c.village))];
  heroChips.innerHTML = `<span class="chip">${en(n)} کلبه</span><span class="chip">منطقه: ${villages.join('، ')} — بابلکنار</span><span class="chip">به‌روزرسانی: 2026-08-01</span>`;
}

function propsHtml(c) {
  const p = c.properties || [];
  const out = [];
  if (c.is_plus) out.push('<span class="badge plus">مـمـتــــاز</span>');
  if (c.is_instant) out.push('<span class="badge instant">رزرو فوری</span>');
  p.forEach(x => {
    const em = PROP_EMOJI[x] || '•';
    out.push(`<span class="badge ${x==='خوش منظره'?'scenic':''}">${em} ${x}</span>`);
  });
  return out.join(' ');
}

function featName(c, x) {
  return (c.feature_desc && c.feature_desc[x]) || FEATURE_FA[x] || x;
}
function featIcons(c) {
  const f = c.features || [];
  const names = f.map(x => featName(c, x)).join('، ');
  return `<span class="en" title="${esc(names)}">${f.length}</span>`;
}

function ratingHtml(c) {
  const r = c.rating;
  if (r === null || r === undefined) return '—';
  const cls = r >= 4.5 ? 'rating-hi' : (r >= 4 ? 'rating-mid' : '');
  return `<span class="${cls}">★ ${r.toFixed(1)}</span>`;
}

function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function renderTable() {
  const rows = getSorted();
  const colors = ['#d4a72c','#c0c0c0','#cd7f32'];
  tbody.innerHTML = rows.map((c, i) => {
    const own = c.own ? '<span class="own-badge">کلبه خودم</span>' : '';
    const occ = c.occupancy_30 === null || c.occupancy_30 === undefined ? '—' :
      `<span class="occ ${occClass(c.occupancy_30)}"><span class="en">${en(c.occupancy_30)}%</span></span>`;
    const disc = (c.current_discount_percent||0) > 0 ? `<span class="disc en">${c.current_discount_percent}%</span>` : '—';
    const rank = i < 3 ? `<span style="display:inline-flex;width:24px;height:24px;border-radius:50%;background:${colors[i]};color:#111;align-items:center;justify-content:center;font-weight:800" class="en">${i+1}</span>` : `<span class="en">${i+1}</span>`;
    const titleLink = `<a class="title-link" href="${c.url}" target="_blank" rel="noopener" title="${esc(c.title)}">${esc(c.title)}</a>`;
    const hostLink = c.host_id ? `<a class="host-link" href="https://www.jajiga.com/user/${c.host_id}" target="_blank" rel="noopener" title="پروفایل ${esc(c.host_name)} در جاجیگا">${esc(c.host_name)}</a>` : (c.host_name||'—');
    return `<tr class="data-row ${own?'own-row':''}" data-id="${c.id}">
      <td>${rank}</td>
      <td class="title">${titleLink}${own}</td>
      <td><span class="village-tag">${c.village||'—'}</span></td>
      <td>${hostLink}</td>
      <td><span class="en">${en(c.min_price)}</span></td>
      <td><span class="en">${en(c.floor_area)}</span>م</td>
      <td><span class="en">${en(c.land_area)}</span>م</td>
      <td><span class="en">${en(c.bedrooms)}</span></td>
      <td><span class="en">${en(c.max_guest_number)}</span></td>
      <td>${featIcons(c)}</td>
      <td>${propsHtml(c)}</td>
      <td>${ratingHtml(c)}</td>
      <td><span class="en">${en(c.reviews)}</span></td>
      <td><span class="en">${en(c.success_books)}</span></td>
      <td>${occ}</td>
      <td>${disc}</td>
    </tr>
    <tr class="detail-row" id="det-${c.id}" style="display:none"><td colspan="16">${detailHtml(c)}</td></tr>`;
  }).join('');
}

function detailHtml(c) {
  const feats = (c.features||[]).map(f => {
    const name = featName(c, f);
    return `<div class="feat-line"><span class="fname">${esc(name)}</span></div>`;
  }).join('');
  const subR = [
    ['دقت توصیف', c.rating_accuracy], ['ارتباط', c.rating_communication], ['پاکیزگی', c.rating_cleanliness],
    ['موقعیت', c.rating_location], ['پذیرش', c.rating_checkin], ['ارزش', c.rating_value],
  ].map(([l,v]) => `<div class="subrating"><span class="lbl">${l}</span><span class="en">${v===null||v===undefined?'—':v.toFixed(1)}</span></div>`).join('');
  const discList = (c.discounts||[]).map(d =>
    `<div class="host-line">تخفیف ${d.percent}٪ — ${d.type||'—'} ${d.min_nights?`(از ${d.min_nights} شب)`:''}</div>`).join('');
  const types = (c.types||[]).join('، ') || '—';
  const regions = (c.regions||[]).join('، ') || '—';
  const geo = c.geo ? `${c.geo.lat}, ${c.geo.lng}` : '—';
  const hostSince = toJalali(c.host_created_at) || '—';
  const rt = c.host_response_time === null || c.host_response_time === undefined ? '—' :
    (c.host_response_time < 60 ? `${c.host_response_time} دقیقه` : `${(c.host_response_time/60).toFixed(1)} ساعت`);
  return `<div class="detail-inner">
    <div class="detail-block"><h4>امکانات (${c.features_count||0})</h4>${feats||'—'}</div>
    <div class="detail-block"><h4>برچسب‌ها و ویژگی‌ها</h4>${propsHtml(c)||'—'}<div class="host-line" style="margin-top:6px"><span class="lbl">نوع:</span> ${types}</div><div class="host-line"><span class="lbl">منطقه:</span> ${regions}</div></div>
    <div class="detail-block"><h4>امتیازهای کاربران</h4>${subR}</div>
    <div class="detail-block"><h4>قیمت و تخفیف</h4>
      <div class="host-line"><span class="lbl">قیمت پایه:</span> <span class="en">${en(c.min_price)}</span> ت/شب</div>
      <div class="host-line"><span class="lbl">تخفیف فعلی:</span> <span class="en">${(c.current_discount_percent||0)}%</span></div>
      ${discList}
      <div class="host-line"><span class="lbl">قانون کنسلی:</span> ${CANCEL[c.cancellation_policy]||c.cancellation_policy||'—'}</div>
      <div class="host-line"><span class="lbl">حداقل/حداکثر اقامت:</span> <span class="en">${c.stays_min||'—'} / ${c.stays_max||'∞'}</span> شب</div>
    </div>
    <div class="detail-block"><h4>میزبان</h4>
      <div class="host-line"><span class="lbl">نام:</span> ${c.host_id ? `<a class="host-link" href="https://www.jajiga.com/user/${c.host_id}" target="_blank" rel="noopener" title="پروفایل ${esc(c.host_name)} در جاجیگا">${esc(c.host_name)}</a>` : (c.host_name||'—')} (${c.host_gender==='male'?'آقا':'خانم'||''})</div>
      <div class="host-line"><span class="lbl">عضویت:</span> ${hostSince}</div>
      <div class="host-line"><span class="lbl">نرخ پذیرش:</span> <span class="en">${c.host_accept_rate??'—'}%</span></div>
      <div class="host-line"><span class="lbl">زمان پاسخ:</span> ${rt}</div>
      <div class="host-line"><span class="lbl">امتیاز ارتباط:</span> <span class="en">${c.host_communication_rate??'—'}</span></div>
    </div>
    <div class="detail-block"><h4>سایر</h4>
      <div class="host-line"><span class="lbl">رزرو موفق:</span> <span class="en">${en(c.success_books)}</span></div>
      <div class="host-line"><span class="lbl">عکس‌ها:</span> <span class="en">${en(c.pictures_count)}</span></div>
      <div class="host-line"><span class="lbl">VR:</span> ${c.vr_photo?'✅':'—'}</div>
      <div class="host-line"><span class="lbl">ویدیو:</span> ${c.video_url?'✅':'—'}</div>
      <div class="host-line"><span class="lbl">مختصات:</span> <span class="en">${geo}</span></div>
      <div class="host-line"><span class="lbl">وضعیت:</span> ${c.status==='active'?'فعال':'غیرفعال'}</div>
      <div class="host-line"><a class="link" href="${c.url}" target="_blank">مشاهده در جاجیگا ↗</a></div>
    </div>
  </div>`;
}

function init() {
  tbody = document.getElementById('tbody');
  headRow = document.getElementById('headRow');
  statsRow = document.getElementById('statsRow');
  searchBox = document.getElementById('searchBox');
  villageFilters = document.getElementById('villageFilters');
  heroChips = document.getElementById('heroChips');
  renderHead();
  searchBox.addEventListener('input', renderTable);
  renderHeroChips();
  renderVillageFilters();
  renderStats();
  renderTable();
  tbody.addEventListener('click', e => {
    const tr = e.target.closest('tr.data-row');
    if (!tr) return;
    const det = document.getElementById('det-' + tr.dataset.id);
    det.style.display = det.style.display === 'none' ? '' : 'none';
  });
}
function cycleSort(k) {
  if (sortKey !== k) {
    sortKey = k;
    const col = SORT_COLS.find(c=>c.key===k);
    sortDir = typeof col.val(DATA[0]) === 'string' ? 1 : -1;  // text: asc first, numeric: desc first
  } else if (sortDir === -1) {
    sortDir = 1;
  } else if (sortDir === 1) {
    sortKey = null; sortDir = -1;
  }
  renderHead(); renderTable();
}
function renderHead() {
  headRow.innerHTML = SORT_COLS.map(c => {
    const arrow = sortKey === c.key ? (sortDir === -1 ? '▼' : '▲') : '';
    return `<th data-key="${c.key}">${c.label}<span class="arrow">${arrow}</span></th>`;
  }).join('');
  headRow.querySelectorAll('th').forEach(th => {
    th.addEventListener('click', () => cycleSort(th.dataset.key));
  });
}
init();
</script>
</body>
</html>
"""

html = HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False))
html = html.replace("__FEATURE_FA__", json.dumps(FEATURE_FA, ensure_ascii=False))
html = html.replace("__PROP_EMOJI__", json.dumps(PROPERTY_EMOJI, ensure_ascii=False))
html = html.replace("__CANCEL__", json.dumps(CANCEL_LABEL, ensure_ascii=False))

with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print(f"OK -> {OUT} ({os.path.getsize(OUT):,} bytes)")
