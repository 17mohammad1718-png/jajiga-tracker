# Jajiga Data Report — PowerPoint Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a visually beautiful PowerPoint (`jajiga-data-report.pptx`) that presents all jajiga-tracker data as an easy-to-read data report. No algorithm, no technical analysis — just data explained visually.

**Architecture:** Node.js + pptxgenjs (installed v4.0.1) generates a native .pptx with charts, big-number callouts, and RTL Persian text. Data is read from `H:\hermes outputs\jajiga_complete_dataset.json` (the aggregated lossless dataset).

**Tech Stack:** Node.js 24 + pptxgenjs 4.0.1, data from aggregated JSON.

---

## Design Direction (بصری)

- **Palette (جنگل مازندران):** سبز جنگلی تیره `2C5F2D` غالب، سبز خزه‌ای `97BC62`، کرم `F5F5F5`، لاجوردی `1E2761` برای اعداد، طلایی `C9A227` برای هایلایت.
- **فونت:** `B Nazanin` برای متن فارسی (روی سیستم کاربر نصب است — در سند ورد قبلاً استفاده شد)، اعداد انگلیسی با فونت monospace برای تمایز.
- **موتیف:** کارت‌های عدد بزرگ (60-72pt) + نمودارهای native pptxgenjs (bar, line, doughnut) + صفحه‌های تیره برای عنوان/پایان، روشن برای محتوا (ساندویچ).
- **اعداد:** همیشه انگلیسی (سلیقه کاربر)، بدون ایموجی، متن فارسی RTL.
- **بدون تحلیل:** فقط توصیف دیتا (تعداد، توزیع، رتبه‌بندی، میانگین) — هیچ همبستگی/الگوریتمی.

---

## Slide Plan (۱۱ اسلاید)

| # | اسلاید | محتوا | المان بصری |
|---|---|---|---|
| 1 | عنوان (تیره) | «گزارش داده‌های بازار اقامتگاه بابل‌کنار» — جاجیگا | پس‌زمینه سبز تیره، ۳ عدد بزرگ تیزر |
| 2 | مرور کلی (۶ عدد بزرگ) | ۳۴۶ میزبان، ۴۶۷ اقامتگاه، ۱۵۷ کلبه ۶ روستا، ۱۰۸ دیتاست قیمت، ۱۱۸ فایل خام، ۶۸ ماه | ۶ کارت عددی ۲×۳ |
| 3 | رشد بازار ۲۰۱۹-۲۰۲۶ | سالانه: میزبان ۴→۳۴۶، اتاق ۲→۴۶۷ | نمودار خطی تجمعی دو سری (native) |
| 4 | توزیع روستاها | تعداد اقامتگاه به تفکیک روستا (۲۰ روستا) | نمودار میله‌ای افقی |
| 5 | ۶ روستای منتخب | سیدکلا ۳۲، قرآن تالار ۱۱، گونه کلا ۳۱، شیردارکلا ۳۴، کاردرکلا ۴۷، امیرکلا ۲ | ۶ کارت با محدوده قیمت |
| 6 | میزبان‌ها — سطوح | تازه‌کار ۱۲۸، مبتدی ۱۱۲، فعال ۸۳، حرفه‌ای ۲۳ | نمودار دونات + نوار |
| 7 | تاپ ۱۰ میزبان | فتحعلی ۱۹۰۵ رزرو … تا مبینا ۳۵۵ | جدول رتبه‌بندی با مدال |
| 8 | دیتاست قیمت ۱۰۸ کلبه | ۴ روستا: میانگین/حداقل/حداکثر قیمت | نمودار میله‌ای گروهی |
| 9 | امکانات | تاپ ۱۲ امکانات (bathroom, electricity, …) | نمودار میله‌ای افقی + کارت |
| 10 | اشغال ۳۰ روز | میانگین ۱۲ روز از ۳۰، max ۷۰ | گیج/کارت عددی + نوار توزیع |
| 11 | پایان (تیره) | خلاصه داده‌ها + منبع | عدد بزرگ ۴۶۷ اقامتگاه |

---

## Tasks

### Task 1: Setup data access
**Files:**
- Create: `scripts/build_pptx_data.js` (reads aggregated JSON, exports key stats)
- Read: `H:\hermes outputs\jajiga_complete_dataset.json`

**Step 1:** Verify pptxgenjs is installed (`npm ls pptxgenjs` — already confirmed v4.0.1).
**Step 2:** Write small data-prep module that computes: counts, yearly growth, rooms-by-village, host levels, top hosts, pricing stats by village, top amenities, occupancy stats.
**Step 3:** Run: `node scripts/build_pptx_data.js --dry` — prints computed stats for eyeball check.
**Verify:** Output numbers match the values already confirmed in this session (346/467/157/108/118, فتحعلی 1905, etc.).

### Task 2: Slide framework + title + overview
**Files:**
- Create: `scripts/build_pptx.js` (main generator, pptxgenjs)

**Step 1:** Set up pptxgenjs: `pres.layout = 'LAYOUT_WIDE'` (13.3×7.5), define palette constants, helper functions (`bigNumber`, `card`, `persianTitle`, `table`, `chart`).
**Step 2:** Slide 1 (dark title) + Slide 2 (6 big-number cards).
**Step 3:** Write to `jajiga-data-report.pptx`, run `python scripts/office/validate.py jajiga-data-report.pptx` (validate script from powerpoint skill).
**Verify:** validate.py passes (no corruption); python-pptx can open and shows 2 slides.

### Task 3: Growth chart + villages distribution
**Files:**
- Modify: `scripts/build_pptx.js`

**Step 1:** Slide 3 — line chart: hosts_cum & rooms_cum per year (2019-2026), Persian labels, `showValue:true`, chartColors from palette, `showLegend:true`.
**Step 2:** Slide 4 — horizontal bar chart of rooms-by-village (top 12 + سایر).
**Step 3:** Re-run + validate.
**Verify:** validate.py passes; open with python-pptx, check chart parts exist.

### Task 4: Village cards + host levels + top hosts
**Files:**
- Modify: `scripts/build_pptx.js`

**Step 1:** Slide 5 — 6 village cards with price ranges (from pricing + all-cabins data).
**Step 2:** Slide 6 — doughnut chart of host levels + side stats.
**Step 3:** Slide 7 — top-10 hosts table with rank medals (gold/silver/bronze per user's dashboard convention).
**Verify:** validate.py passes.

### Task 5: Pricing + amenities + occupancy + closing
**Files:**
- Modify: `scripts/build_pptx.js`

**Step 1:** Slide 8 — grouped bar: min/avg/max price per village (4 villages).
**Step 2:** Slide 9 — top-12 amenities horizontal bar.
**Step 3:** Slide 10 — occupancy 30-day stat callout.
**Step 4:** Slide 11 — dark closing slide.
**Verify:** validate.py passes; full 11 slides open in python-pptx.

### Task 6: QA + finalize
**Files:**
- Read: `jajiga-data-report.pptx`

**Step 1:** `python scripts/office/validate.py jajiga-data-report.pptx` — must pass.
**Step 2:** Extract text via python-pptx and check: all Persian labels, no emoji, no lorem/placeholder, all 11 slides present, numbers English.
**Step 3:** Deliver via MEDIA: path.
**Verify:** validate passes, text extraction clean, slide count = 11.

---

## Risks

1. **فونت B Nazanin در محیط QA نیست** — LibreOffice روی این سیستم نصب نیست، پس رندر بصری نمی‌توانم انجام دهم. Mitigation: validate.py + python-pptx structural check + متن استخراجی؛ فونت روی سیستم کاربر (ویندوز) موجود است.
2. **RTL در pptxgenjs** — متن فارسی باید با `align: 'right'` و `rtlMode` تنظیم شود؛ در validate چک می‌شود.
3. **Overflow متن فارسی** — اندازه فونت‌ها محافظه‌کارانه (اعداد بزرگ 48-60pt، متن 14-16pt) + بررسی متن استخراجی.

---

## Out of Scope
- الگوریتم قیمت‌گذاری، همبستگی‌ها، تحلیل آماری عمیق (طبق قرار قبلی — فاز ۱ فقط داده)
- ایموجی، تصاویر، فایل‌های خارجی

**Plan ready. Say "go" to start implementation, or tell me what to change.**
