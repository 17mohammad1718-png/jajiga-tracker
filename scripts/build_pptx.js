#!/usr/bin/env node
/**
 * Build jajiga-data-report.pptx — a visually polished, DATA-ONLY Persian deck
 * presenting the jajiga-tracker aggregated dataset. No analysis, no algorithm.
 */
const pptxgen = require('pptxgenjs');
const fs = require('fs');

const DATA_PATH = 'H:/hermes outputs/jajiga_complete_dataset.json';
const OUT = 'jajiga-data-report.pptx';

const data = JSON.parse(fs.readFileSync(DATA_PATH, 'utf8'));

// ------------------------------------------------------------- palette
const GREEN   = '2C5F2D';
const MOSS    = '97BC62';
const NAVY    = '1E2761';
const GOLD    = 'C9A227';
const WHITE   = 'FFFFFF';
const DARK    = '1B3A1B';
const GRAY    = '6B7280';
const LIGHT   = 'F2F6EF';
const PERSIAN = 'B Nazanin';
const MONO    = 'Consolas';

const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE'; // 13.3 x 7.5 in
pres.author = 'Hermes';
pres.title = 'گزارش داده‌های بازار اقامتگاه بابل‌کنار';

const W = 13.3, H = 7.5;

// ------------------------------------------------------------- helpers
function shadow() {
  return { type: 'outer', color: 'D8D8D8', blur: 8, offset: 3, angle: 45, opacity: 0.35 };
}

function fmt(n) {
  if (n === null || n === undefined) return '—';
  return n.toLocaleString('en-US');
}

function header(slide, section, title) {
  slide.addShape(pres.ShapeType.ellipse, {
    x: 0.6, y: 0.45, w: 0.65, h: 0.65,
    fill: { color: GREEN }, line: { type: 'none' }, shadow: shadow(),
  });
  slide.addText(section, { x: 0.6, y: 0.45, w: 0.65, h: 0.65, align: 'center', valign: 'mid',
    fontFace: MONO, fontSize: 18, bold: true, color: WHITE, margin: 0 });
  slide.addText(title, { x: 1.6, y: 0.42, w: 11.1, h: 0.7, align: 'right', valign: 'mid',
    fontFace: PERSIAN, fontSize: 28, bold: true, color: NAVY, rtlMode: true, margin: 0 });
}

function footer(slide) {
  slide.addText('منبع: دیتاست جاجیگا — بابل‌کنار | مرداد 1405', {
    x: 0.5, y: 7.02, w: 12.3, h: 0.32, align: 'right',
    fontFace: PERSIAN, fontSize: 9, color: '9CA3AF', rtlMode: true, margin: 0 });
}

function card(slide, x, y, w, h, number, label, numColor, numSize, labelSize) {
  slide.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, fill: { color: LIGHT }, line: { color: 'E5E5E5', width: 0.75 },
    rectRadius: 0.08, shadow: shadow(),
  });
  slide.addText(number, { x, y: y + 0.12, w, h: h * 0.52, align: 'center', valign: 'mid',
    fontFace: MONO, fontSize: numSize, bold: true, color: numColor, margin: 0 });
  slide.addText(label, { x: x + 0.15, y: y + h * 0.55, w: w - 0.3, h: h * 0.4, align: 'center',
    valign: 'top', fontFace: PERSIAN, fontSize: labelSize, color: GRAY, rtlMode: true, margin: 0 });
}

// ------------------------------------------------------------- compute stats
const hostsDb = data.hosts_db.hosts;                       // 346 full host profiles
const supplyHosts = data.supply.hosts;                     // 346 (supply timeline)
const supplyRooms = data.supply.rooms;                     // 467
const allCabins = data.all_cabins;                         // {meta, villages}
const pricing = data.pricing.json;                         // 108
const months = data.supply.months;                         // 68

const totalCabins = Object.values(allCabins.villages).reduce((a, v) => a + v.length, 0);
const rawTotal = Object.values(data.raw_pricing).reduce((a, v) => a + v.length, 0);

// yearly growth
const years = ['2019', '2020', '2021', '2022', '2023', '2024', '2025', '2026'];
const yearly = {};
for (const y of years) yearly[y] = { hosts: 0, rooms: 0 };
for (const m of months) {
  const y = m.key.slice(0, 4);
  if (yearly[y]) { yearly[y].hosts = m.hosts_cum; yearly[y].rooms = m.rooms_cum; }
}
const hostsCum = years.map(y => yearly[y].hosts);
const roomsCum = years.map(y => yearly[y].rooms);

// rooms by village (all 20, sorted desc)
const villageCounts = {};
for (const r of supplyRooms) villageCounts[r.village] = (villageCounts[r.village] || 0) + 1;
const villageSorted = Object.entries(villageCounts).sort((a, b) => b[1] - a[1]);

// host levels
const levelCounts = {};
for (const h of supplyHosts) {
  const lv = h.host_level || 'نامشخص';
  levelCounts[lv] = (levelCounts[lv] || 0) + 1;
}
const levelOrder = ['تازه‌کار', 'مبتدی', 'فعال', 'حرفه‌ای'];
const levelLabels = levelOrder.filter(l => levelCounts[l]);
const levelValues = levelLabels.map(l => levelCounts[l]);

// top 10 hosts (by total_books)
const topHosts = [...supplyHosts].sort((a, b) => (b.total_books || 0) - (a.total_books || 0)).slice(0, 10);

// pricing per village (min/avg/max of min_price)
const prByV = {};
for (const c of pricing) {
  if (!prByV[c.village]) prByV[c.village] = [];
  prByV[c.village].push(c.min_price || 0);
}
const prVillages = Object.keys(prByV); // order as in dataset
const prMin = prVillages.map(v => Math.min(...prByV[v]));
const prAvg = prVillages.map(v => Math.round(prByV[v].reduce((a, b) => a + b, 0) / prByV[v].length));
const prMax = prVillages.map(v => Math.max(...prByV[v]));

// village cards (from all_cabins — covers all 6 selected villages)
const villageCards = [];
for (const [vname, cabins] of Object.entries(allCabins.villages)) {
  const prices = cabins.map(c => c.price).filter(Boolean);
  villageCards.push({
    name: vname,
    n: cabins.length,
    min: prices.length ? Math.min(...prices) : null,
    max: prices.length ? Math.max(...prices) : null,
  });
}

// amenities top 12 (English key -> Persian label)
const amenityLabels = {
  bathroom: 'سرویس بهداشتی', electricity: 'برق', essentials: 'ملزومات پایه',
  heating: 'گرمایش', kitchen: 'آشپزخانه', refrigerator: 'یخچال', water: 'آب',
  islamictoilet: 'سرویس ایرانی', stave: 'اجاق', cooler: 'کولر',
  furniture: 'مبلمان', parking: 'پارکینگ',
};
const amenityCounts = {};
for (const c of pricing) for (const f of (c.features || [])) amenityCounts[f] = (amenityCounts[f] || 0) + 1;
const amenityTop = Object.entries(amenityCounts).sort((a, b) => b[1] - a[1]).slice(0, 12);
const amenityLabelsL = amenityTop.map(([k]) => amenityLabels[k] || k);
const amenityValues = amenityTop.map(([, v]) => v);

// occupancy
const occs = pricing.map(c => c.occupancy_30 || 0);
const occAvg = Math.round(occs.reduce((a, b) => a + b, 0) / occs.length);
const occWith = occs.filter(v => v > 0).length;
const occZero = occs.length - occWith;
const occBuckets = [0, 0, 0, 0];
for (const v of occs) {
  if (v === 0) occBuckets[0]++;
  else if (v <= 9) occBuckets[1]++;
  else if (v <= 19) occBuckets[2]++;
  else occBuckets[3]++;
}
const occBucketLabels = ['0 روز', '1 تا 9', '10 تا 19', '20+'];
const proShare = Math.round((levelCounts['حرفه‌ای'] || 0) / supplyHosts.length * 100);

// ------------------------------------------------------------- SLIDE 1 — title
{
  const s = pres.addSlide();
  s.background = { color: DARK };
  s.addShape(pres.ShapeType.ellipse, { x: 10.2, y: -1.6, w: 4.6, h: 4.6, fill: { color: GREEN }, transparency: 45, line: { type: 'none' } });
  s.addShape(pres.ShapeType.ellipse, { x: -1.8, y: 5.0, w: 3.8, h: 3.8, fill: { color: MOSS }, transparency: 55, line: { type: 'none' } });
  s.addShape(pres.ShapeType.ellipse, { x: 11.6, y: 4.4, w: 2.2, h: 2.2, fill: { color: GOLD }, transparency: 65, line: { type: 'none' } });

  s.addText('گزارش داده‌های بازار اقامتگاه', { x: 1, y: 1.45, w: 11.3, h: 1.15, align: 'center', fontFace: PERSIAN, fontSize: 44, bold: true, color: WHITE, rtlMode: true, margin: 0 });
  s.addText('بابل‌کنار — جاجیگا', { x: 1, y: 2.62, w: 11.3, h: 0.7, align: 'center', fontFace: PERSIAN, fontSize: 24, color: MOSS, rtlMode: true, margin: 0 });

  const teasers = [
    { n: '346', l: 'میزبان' },
    { n: '467', l: 'اقامتگاه' },
    { n: '157', l: 'کلبه در 6 روستا' },
  ];
  teasers.forEach((t, i) => {
    const x = 1.3 + i * 3.85;
    s.addShape(pres.ShapeType.roundRect, { x, y: 4.55, w: 3.3, h: 1.65, fill: { color: WHITE, transparency: 10 }, rectRadius: 0.1, line: { color: WHITE, width: 0.5 } });
    s.addText(t.n, { x, y: 4.7, w: 3.3, h: 0.85, align: 'center', fontFace: MONO, fontSize: 42, bold: true, color: GOLD, margin: 0 });
    s.addText(t.l, { x, y: 5.62, w: 3.3, h: 0.45, align: 'center', fontFace: PERSIAN, fontSize: 15, color: 'E5E5E5', rtlMode: true, margin: 0 });
  });

  s.addText('مستندسازی دیتاست — فقط داده، بدون تحلیل | منبع: jajiga_complete_dataset.json', { x: 1, y: 6.6, w: 11.3, h: 0.4, align: 'center', fontFace: PERSIAN, fontSize: 11, color: 'C8C8C8', rtlMode: true, margin: 0 });
}

// ------------------------------------------------------------- SLIDE 2 — overview
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  header(s, '1', 'مرور کلی دیتاست');
  const items = [
    { n: fmt(supplyHosts.length), l: 'میزبان با پروفایل کامل' },
    { n: fmt(supplyRooms.length), l: 'اقامتگاه' },
    { n: fmt(totalCabins), l: 'کلبه در 6 روستای منتخب' },
    { n: fmt(pricing.length), l: 'کلبه در دیتاست قیمت‌گذاری' },
    { n: fmt(rawTotal), l: 'فایل خام API اقامتگاه' },
    { n: fmt(months.length), l: 'ماه روند عرضه (1398 تا 1405)' },
  ];
  items.forEach((o, i) => {
    const col = i % 3, row = Math.floor(i / 3);
    card(s, 0.8 + col * 4.1, 1.55 + row * 2.55, 3.65, 2.15, o.n, o.l, i === 4 ? GREEN : NAVY, 42, 14);
  });
  footer(s);
}

// ------------------------------------------------------------- SLIDE 3 — growth
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  header(s, '2', 'رشد بازار 1398 تا 1405');
  s.addChart(pres.ChartType.line, [
    { name: 'میزبان', labels: years, values: hostsCum },
    { name: 'اقامتگاه', labels: years, values: roomsCum },
  ], {
    x: 1.0, y: 1.45, w: 11.3, h: 4.7,
    chartColors: [MOSS, GOLD],
    lineSize: 3, lineSmooth: false,
    showLegend: true, legendPos: 't', legendFontFace: PERSIAN, legendFontSize: 13, legendColor: NAVY,
    showValue: false,
    catAxisLabelColor: NAVY, catAxisLabelFontFace: PERSIAN, catAxisLabelFontSize: 12,
    valAxisLabelColor: GRAY, valAxisLabelFontFace: MONO, valAxisLabelFontSize: 10,
    valGridLine: { color: 'E5E7EB', size: 1 },
    catGridLine: { style: 'none' },
    valAxisLabelFormatCode: '#,##0',
  });
  s.addText(`از ${hostsCum[0]} میزبان و ${roomsCum[0]} اقامتگاه در 1398 به ${hostsCum[7]} میزبان و ${roomsCum[7]} اقامتگاه در 1405`, {
    x: 1, y: 6.35, w: 11.3, h: 0.5, align: 'center', fontFace: PERSIAN, fontSize: 13, color: GRAY, rtlMode: true, margin: 0 });
  footer(s);
}

// ------------------------------------------------------------- SLIDE 4 — villages
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  header(s, '3', 'اقامتگاه‌ها به تفکیک روستا — 20 روستا');
  s.addChart(pres.ChartType.bar, [
    { name: 'اقامتگاه', labels: villageSorted.map(v => v[0]), values: villageSorted.map(v => v[1]) },
  ], {
    x: 0.7, y: 1.3, w: 11.9, h: 5.4,
    barDir: 'bar',
    chartColors: [GREEN],
    showValue: true, dataLabelPosition: 'outEnd', dataLabelColor: NAVY,
    dataLabelFontFace: MONO, dataLabelFontSize: 9,
    showLegend: false,
    catAxisLabelColor: NAVY, catAxisLabelFontFace: PERSIAN, catAxisLabelFontSize: 10,
    valAxisLabelColor: GRAY, valAxisLabelFontFace: MONO, valAxisLabelFontSize: 9,
    valGridLine: { color: 'E5E7EB', size: 1 },
    catGridLine: { style: 'none' },
  });
  footer(s);
}

// ------------------------------------------------------------- SLIDE 5 — 6 village cards
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  header(s, '4', '6 روستای منتخب — تعداد کلبه و محدوده قیمت');
  villageCards.forEach((v, i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = 0.7 + col * 4.1, y = 1.5 + row * 2.6, w = 3.8, h = 2.25;
    s.addShape(pres.ShapeType.roundRect, { x, y, w, h, fill: { color: LIGHT }, line: { color: 'E5E5E5', width: 0.75 }, rectRadius: 0.08, shadow: shadow() });
    s.addText(v.name, { x, y: y + 0.15, w, h: 0.5, align: 'center', fontFace: PERSIAN, fontSize: 18, bold: true, color: GREEN, rtlMode: true, margin: 0 });
    s.addText(fmt(v.n), { x, y: y + 0.55, w, h: 0.8, align: 'center', fontFace: MONO, fontSize: 36, bold: true, color: NAVY, margin: 0 });
    s.addText('کلبه', { x, y: y + 1.3, w, h: 0.35, align: 'center', fontFace: PERSIAN, fontSize: 12, color: GRAY, rtlMode: true, margin: 0 });
    s.addText(
      v.min != null ? `${fmt(v.min)} تا ${fmt(v.max)} تومان` : 'قیمت نامشخص',
      { x: x + 0.15, y: y + 1.65, w: w - 0.3, h: 0.45, align: 'center', fontFace: MONO, fontSize: 10.5, color: GRAY, rtlMode: true, margin: 0 });
  });
  footer(s);
}

// ------------------------------------------------------------- SLIDE 6 — host levels
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  header(s, '5', 'سطوح میزبان‌ها — 346 میزبان');
  s.addChart(pres.ChartType.doughnut, [
    { name: 'میزبان', labels: levelLabels, values: levelValues },
  ], {
    x: 0.7, y: 1.5, w: 6.6, h: 5.0,
    holeSize: 55,
    chartColors: [MOSS, GREEN, NAVY, GOLD],
    showLegend: true, legendPos: 'b', legendFontFace: PERSIAN, legendFontSize: 13, legendColor: NAVY,
    showValue: true, dataLabelPosition: 'ctr', dataLabelColor: WHITE, dataLabelFontFace: MONO, dataLabelFontSize: 11,
  });
  const stats = [
    { n: '346', l: 'کل میزبان' },
    { n: `${levelCounts['حرفه‌ای'] || 0}`, l: `میزبان حرفه‌ای (${proShare}٪ بازار)` },
    { n: fmt(Math.max(...supplyHosts.map(h => h.total_books || 0))), l: 'بیشترین رزرو موفق — فتحعلی' },
  ];
  stats.forEach((st, i) => card(s, 8.1, 1.7 + i * 1.75, 4.3, 1.5, st.n, st.l, GREEN, 30, 13));
  footer(s);
}

// ------------------------------------------------------------- SLIDE 7 — top hosts
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  header(s, '6', 'میزبان‌های برتر بابل‌کنار — 10 نفر اول');
  const medal = [GOLD, 'C0C0C0', 'CD7F32'];
  const rows = [[
    { text: 'رتبه', options: { bold: true, fontFace: PERSIAN, fill: { color: GREEN }, color: WHITE, align: 'center' } },
    { text: 'نام میزبان', options: { bold: true, fontFace: PERSIAN, fill: { color: GREEN }, color: WHITE, align: 'right', rtlMode: true } },
    { text: 'تعداد اقامتگاه', options: { bold: true, fontFace: PERSIAN, fill: { color: GREEN }, color: WHITE, align: 'center' } },
    { text: 'رزرو موفق', options: { bold: true, fontFace: PERSIAN, fill: { color: GREEN }, color: WHITE, align: 'center' } },
    { text: 'سطح', options: { bold: true, fontFace: PERSIAN, fill: { color: GREEN }, color: WHITE, align: 'center' } },
  ]];
  topHosts.forEach((h, i) => {
    const rankFill = i < 3 ? medal[i] : 'F3F4F6';
    const rankColor = i < 3 ? WHITE : GRAY;
    rows.push([
      { text: String(i + 1), options: { fontFace: MONO, bold: true, fill: { color: rankFill }, color: rankColor, align: 'center' } },
      { text: h.name || '', options: { fontFace: PERSIAN, color: NAVY, align: 'right', rtlMode: true } },
      { text: fmt(h.rooms_count), options: { fontFace: MONO, align: 'center' } },
      { text: fmt(h.total_books), options: { fontFace: MONO, bold: true, color: GREEN, align: 'center' } },
      { text: h.host_level || '', options: { fontFace: PERSIAN, align: 'center' } },
    ]);
  });
  s.addTable(rows, {
    x: 1.0, y: 1.4, w: 11.3,
    colW: [1.1, 4.2, 2.3, 2.0, 1.7],
    rowH: 0.5,
    border: { type: 'solid', color: 'E5E7EB', pt: 0.5 },
    fontSize: 12, valign: 'mid', autoPage: false,
  });
  footer(s);
}

// ------------------------------------------------------------- SLIDE 8 — pricing
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  header(s, '7', 'قیمت کلبه‌ها به تفکیک روستا — 108 کلبه');
  s.addChart(pres.ChartType.bar, [
    { name: 'حداقل', labels: prVillages, values: prMin.map(v => +(v / 1e6).toFixed(2)) },
    { name: 'میانگین', labels: prVillages, values: prAvg.map(v => +(v / 1e6).toFixed(2)) },
    { name: 'حداکثر', labels: prVillages, values: prMax.map(v => +(v / 1e6).toFixed(2)) },
  ], {
    x: 0.8, y: 1.45, w: 11.7, h: 4.75,
    chartColors: [MOSS, GREEN, NAVY],
    showLegend: true, legendPos: 't', legendFontFace: PERSIAN, legendFontSize: 13, legendColor: NAVY,
    showValue: true, dataLabelPosition: 'outEnd', dataLabelColor: NAVY,
    dataLabelFontFace: MONO, dataLabelFontSize: 9,
    catAxisLabelColor: NAVY, catAxisLabelFontFace: PERSIAN, catAxisLabelFontSize: 12,
    valAxisLabelColor: GRAY, valAxisLabelFontFace: MONO, valAxisLabelFontSize: 9,
    valGridLine: { color: 'E5E7EB', size: 1 },
    catGridLine: { style: 'none' },
  });
  s.addText('واحد: میلیون تومان — قیمت پایه هر شب (min_price) — بدون تخفیف', {
    x: 1, y: 6.35, w: 11.3, h: 0.5, align: 'center', fontFace: PERSIAN, fontSize: 13, color: GRAY, rtlMode: true, margin: 0 });
  footer(s);
}

// ------------------------------------------------------------- SLIDE 9 — amenities
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  header(s, '8', 'پرکاربردترین امکانات — از 108 کلبه');
  s.addChart(pres.ChartType.bar, [
    { name: 'کلبه', labels: amenityLabelsL, values: amenityValues },
  ], {
    x: 0.7, y: 1.3, w: 11.9, h: 5.4,
    barDir: 'bar',
    chartColors: [MOSS],
    showValue: true, dataLabelPosition: 'outEnd', dataLabelColor: NAVY,
    dataLabelFontFace: MONO, dataLabelFontSize: 10,
    showLegend: false,
    catAxisLabelColor: NAVY, catAxisLabelFontFace: PERSIAN, catAxisLabelFontSize: 12,
    valAxisLabelColor: GRAY, valAxisLabelFontFace: MONO, valAxisLabelFontSize: 9,
    valGridLine: { color: 'E5E7EB', size: 1 },
    catGridLine: { style: 'none' },
  });
  footer(s);
}

// ------------------------------------------------------------- SLIDE 10 — occupancy
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  header(s, '9', 'وضعیت اشغال — 30 روز گذشته');
  const occCards = [
    { n: fmt(occAvg), l: 'میانگین روز اشغال از 30 روز' },
    { n: fmt(occWith), l: `کلبه با رزرو در 30 روز اخیر (از ${fmt(pricing.length)})` },
    { n: fmt(occZero), l: 'کلبه بدون رزرو اخیر' },
  ];
  occCards.forEach((o, i) => card(s, 0.8 + i * 4.1, 1.5, 3.65, 2.0, o.n, o.l, i === 0 ? GREEN : NAVY, 38, 12.5));
  s.addShape(pres.ShapeType.roundRect, { x: 0.8, y: 4.0, w: 11.7, h: 2.7, fill: { color: LIGHT }, line: { color: 'E5E5E5', width: 0.75 }, rectRadius: 0.08, shadow: shadow() });
  s.addText('توزیع کلبه‌ها بر اساس روزهای اشغال', { x: 0.8, y: 4.15, w: 11.7, h: 0.45, align: 'right', fontFace: PERSIAN, fontSize: 14, bold: true, color: NAVY, rtlMode: true, margin: 0 });
  s.addChart(pres.ChartType.bar, [
    { name: 'کلبه', labels: occBucketLabels, values: occBuckets },
  ], {
    x: 1.4, y: 4.65, w: 10.4, h: 1.95,
    chartColors: [GREEN],
    showValue: true, dataLabelPosition: 'outEnd', dataLabelColor: NAVY,
    dataLabelFontFace: MONO, dataLabelFontSize: 11,
    showLegend: false,
    catAxisLabelColor: NAVY, catAxisLabelFontFace: PERSIAN, catAxisLabelFontSize: 11,
    valAxisLabelColor: GRAY, valAxisLabelFontFace: MONO, valAxisLabelFontSize: 8,
    valGridLine: { color: 'E5E7EB', size: 1 },
    catGridLine: { style: 'none' },
  });
  footer(s);
}

// ------------------------------------------------------------- SLIDE 11 — closing
{
  const s = pres.addSlide();
  s.background = { color: DARK };
  s.addShape(pres.ShapeType.ellipse, { x: 9.8, y: -1.4, w: 5, h: 5, fill: { color: GREEN }, transparency: 50, line: { type: 'none' } });
  s.addShape(pres.ShapeType.ellipse, { x: -1.5, y: 5.4, w: 3.6, h: 3.6, fill: { color: MOSS }, transparency: 60, line: { type: 'none' } });
  s.addText(fmt(supplyRooms.length), { x: 1, y: 1.75, w: 11.3, h: 1.6, align: 'center', fontFace: MONO, fontSize: 90, bold: true, color: GOLD, margin: 0 });
  s.addText('اقامتگاه در بازار بابل‌کنار', { x: 1, y: 3.45, w: 11.3, h: 0.7, align: 'center', fontFace: PERSIAN, fontSize: 27, bold: true, color: WHITE, rtlMode: true, margin: 0 });
  s.addText('گزارش داده‌ها — جاجیگا | مرداد 1405 | منبع: jajiga_complete_dataset.json', { x: 1, y: 5.15, w: 11.3, h: 0.5, align: 'center', fontFace: PERSIAN, fontSize: 13, color: 'C8C8C8', rtlMode: true, margin: 0 });
}

// ------------------------------------------------------------- save
pres.writeFile({ fileName: OUT }).then(() => {
  const sz = fs.statSync(OUT).size;
  console.log(`✅ Deck saved: ${OUT} (${(sz / 1024).toFixed(0)} KB)`);
  console.log(`   slides: 11 | hosts: ${supplyHosts.length} | rooms: ${supplyRooms.length}`);
}).catch(err => {
  console.error('❌ writeFile failed:', err);
  process.exit(1);
});