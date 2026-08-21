# داشبورد تحلیل نظرات جاجیگا — Implementation Plan

> **For Hermes:** اجرای task-by-task؛ پس از هر task بیلد/تأیید؛ بعد از تأیید کاربر مرحله بعد.

**Goal:** یک داشبورد تکفایل RTL تیره که نظرات یک کلبهٔ جاجیگا را تحلیل میکند (توزیع امتیاز، روند زمانی، کلیدواژهها، جدول کامل نظرات با فیلتر و سورت) — اول برای وانکوه (3151760)، بعد عمومی برای هر اتاق.

**Architecture:** دیتا با `scripts/fetch_reviews.py` (وجود دارد — آرگومان room id میگیرد) در `data/reviews/{id}_reviews.json` ذخیره میشود. اسکریپت جدید `scripts/build_reviews_dashboard.py` آمار را محاسبه و به همراه خود نظرات داخل تکفایل `reviews-dashboard.html` تزریق میکند (embed از `<script type="application/json" id="revdata">` + `JSON.parse` — نه template literal، طبق pitfall شناختهشده). نمودارها pure CSS/JS بدون کتابخانه (مطابق داشبوردهای قبلی). تم تیره با پالت موجود: `--bg:#0d1117`، فونت Vazirmatn.

**Tech Stack:** Python 3.11 (استاندارد لایبرری فقط)، HTML/CSS/JS تکفایل، بدون CDN، بدون Chart.js.

---

## دامنه (Scope)

**IN:**
- داشبورد ثابت برای 3151760 (وانکوه رامسر) از 359 نظر موجود
- عمومیسازی: بیلدر هر room id را میپذیرد؛ متای اتاق (عنوان/میزبان/شهر) از `data/rooms_meta_cache.json` یا `/api/room/{id}`
- جدول کامل نظرات (تاریخ شمسی، کاربر، امتیاز، متن، پاسخ میزبان) با فیلتر (امتیاز، پاسخ میزبان، سال شمسی، جستجوی متن) و سورت همه ستونها (▼→▲→reset)
- نمودار: توزیع امتیاز، روند ماهانه نظرات، کلیدواژههای پرتکرار
- اعداد انگلیسی monospace (`.en` span)، همه سلولها وسطچین (جز متن نظر = راستچین مثل قانون host-name)، sticky header
- یادداشت شفافیت: API 359 نظر میدهد ولی کارت سایت 402 دارد

**OUT:**
- تحلیل کیفی/الگوریتم (فاز داده فقط)
- مقایسه چند کلبه در یک داشبورد (فاز بعد — YAGNI)
- مدال طلا/نقره/برنز ردیفهای برتر (اینجا بیمعنی است چون متریک امتیاز در ۵ قفل میشود)
- فیلتر بازه تاریخ با تقویم شمسی popup (فعلاً چیپ سال کافی است؛ متغیر وابسته به نیاز کاربر)
- خروجی Excel/CSV (در صورت درخواست جداگانه)

## فایلهای پروژه

| نقش | مسیر |
|---|---|
| دیتا (موجود) | `data/reviews/3151760_reviews.json` (359 نظر) |
| فچر عمومی (موجود) | `scripts/fetch_reviews.py` (پارامتر: room id) |
| **جدید — بیلدر** | `scripts/build_reviews_dashboard.py` |
| **جدید — خروجی** | `reviews-dashboard.html` (ریشه پروژه) |
| **جدید — کش متا** | `data/rooms_meta_cache.json` (اختیاری، ساختهشده در Task 4) |
| پلن | `.hermes/plans/2026-08-13_221600-reviews-dashboard.md` |

---

## Task 1: بررسی دیتای ورودی و ساختار JSON نظرات

**Objective:** اطمینان از شکل دقیق `data/reviews/3151760_reviews.json` تا بیلدر روی فیلدهای واقعی بنویسد.

**Files:**
- Read: `data/reviews/3151760_reviews.json` (بند اول + یک رکورد sample)

**Step 1:** با `python scripts/show_reviews_shape.py` (یا یک دستور `python -c` یکبارمصرف) فیلدهای رکورد را چاپ کنید:
```python
{ id, content, created_at, user.id, user.name, host_reply.content, host_reply.created_at, rating }
```
**Step 2:** تأیید: `rating` مقادیر اعشاری (4.5, 4.8, 5) دارد؛ `host_reply` در بعضی رکوردها غایب است؛ `created_at` فرمت ISO.

**Verification:** خروجی چاپشده با ساختار نمونهٔ ذکرشده در `references/jajiga-reviews-hosts-api.md` یکسان باشد.

---

## Task 2: هستهٔ بیلدر — محاسبه آمار

**Objective:** `scripts/build_reviews_dashboard.py` ساخته شود: بارگذاری JSON، محاسبه همهٔ آمار، خروجی dict.

**Files:**
- Create: `scripts/build_reviews_dashboard.py`

**Step 1 (کد):** تابع `compute_stats(reviews)`:
- `total`, `avg_all` (میانگین همه), `avg_last_year` (365 روز قبل از `date.today()`), `avg_2026` (اختیاری)
- توزیع امتیاز: `Counter(round(r.rating,1))` + تعداد دقیق 5.0 و زیر 5
- نظرات ماهانه: `Counter(created_at[:7])` (برای نمودار روند)
- سال شمسی هر نظر (الگوریتم g2j — کپی از `references/jajiga-hosts-dashboard.md`)
- نرخ پاسخ میزبان: `host_reply` دارد/ندارد
- کاربر یکتا + کاربران با چند نظر (لیست name+count+YOTs)
- کلیدواژهها: لیست curated («استخر», «تمیز», «میزبان», «برخورد», «منظره», «جاده», «طبیعت», «گرون», «ارزان», «پیشنهاد», «آب گرم», «ساکت») + استخراج خودکار 15 توکن پرتکرار پس از حذف stopwords فارسی (لیست کوچک: «و», «که», «از», «با», «به», «این», «بود», «روی», «کردم», «شد», «ما», «من», ...)

**Step 2:** `main()` با `argparse --room` (پیشفرض 3151760)، خواندن `data/reviews/{room}_reviews.json`. اگر فایل نبود: پیام فارسی «ابتدا scripts/fetch_reviews.py را اجرا کنید» + exit 1.

**Verification:** `python scripts/build_reviews_dashboard.py --room 3151760` — چاپ خلاصه آمار؛ میانگین کل ≈ 4.90، یک سال اخیر ≈ 4.97 مطابق محاسبات قبلی.

---

## Task 3: اسکلت HTML + هدر و KPI

**Objective:** اسکلت تکفایل RTL تیره با هدر اتاق و 6 کارت KPI.

**Files:**
- Modify: `scripts/build_reviews_dashboard.py` (بخش render)
- Create: `reviews-dashboard.html` (خروجی بیلدر — نه دستی)

**Step 1 (کد — داخل بیلدر):** قالب HTML با:
- `<html lang="fa" dir="rtl">`, فونت `Vazirmatn` با fallback Tahoma (لینک گوگل فونت + fallback آفلاین)
- CSS متغیرها: `--bg:#0d1117; --panel:#161b22; --border:#21262d; --teal:#0d9488; --text:#e6edf3; --muted:#8b949e; --gold:#f0b429; --silver:#a8b3c0; --bronze:#c07a4b`
- اسکرولبار تیره سفارشی (استاندارد اجباری کاربر: track `#0b1526`, thumb گرادیان `#475569→#334155`, hover `#5b6f8f→#475569`, گوشه `#0b1526`, `scrollbar-gutter: stable`)
- embed دیتا: `<script type="application/json" id="revdata">…</script>` + `const DATA = JSON.parse(...)`
- هدر: عنوان کلبه لینک آبی → `/room/{id}`، میزبان لینک نارنجی → `/user/{host_id}`, چیپ شهر/قیمت/مساحت/رزرو
- 6 کارت KPI با آیکون tinted (مثل hosts v3): کل نظرات، میانگین کل (monospace)، میانگین یک سال اخیر + badge «نمایش سایت», ٪امتیاز ۵، نرخ پاسخ میزبان، کاربر یکتا

**Verification:** بیلد اجرا شود؛ `reviews-dashboard.html` ساخته شود؛ grep کنید `<title>` و `id="revdata"` موجود است.

---

## Task 4: متا اتاق — کش + فچ عمومی

**Objective:** بیلدر متای اتاق را از کش میخواند یا از API میگیرد — مبنای عمومیسازی.

**Files:**
- Modify: `scripts/build_reviews_dashboard.py`
- Create (کش): `data/rooms_meta_cache.json`

**Step 1 (کد):** تابع `load_room_meta(room_id)`:
- اول `data/rooms_meta_cache.json` (dict id→meta)؛ اگر بود استفاده کن
- نبود: `GET https://api.jajiga.com/api/room/{id}` (UA همان)؛ استخراج `title, host{id,name}, price, floor_area, guest_number, success_books, geo, properties[]`؛ ذخیره در کش (فقط در صورت موفقیت)
- خطا: fallback به `data/top_rooms_sweep.json` (در صورت وجود id)؛ آخرین راه: عنوان «اتاق {id}»

**Step 2:** برای 3151760 کش اولیه را بساز (عنوان/میزبان رویا قبلاً از API گرفته شده — میتوان دستی seed کرد یا فچ مجدد).

**Verification:** اجرای بیلدر — بدون تماس شبکه (کش) عنوان درست «کلبه چوبی استخردار در رامسر - وانکوه» نمایش داده شود؛ `data/rooms_meta_cache.json` ساخته و replayable باشد.

---

## Task 5: نمودارها (pure CSS) — توزیع امتیاز و روند ماهانه

**Objective:** دو پنل نمودار بدون کتابخانه.

**Files:**
- Modify: `scripts/build_reviews_dashboard.py` (HTML نمودارها + JS محاسبه)

**Step 1 (کد):** توزیع امتیاز: 5 ستون عمودی (`1..5`) ارتفاع نسبی از counts؛ ستون ۵ با رنگ teal برجسته + hover tooltip count؛ زیر هر ستون «از ۵» / «۴» / ...؛ خط نشانگر میانگین (`avg_all`) روی نمودار.
**Step 2 (کد):** روند ماهانه: نوار افقی اسکرولشونده بر اساس ماه (برچسب ماه شمسی + تعداد). ماهها با فاصلهٔ منظم؛ ارتفاع bar نسبی به max. (احتمالاً 6+ سال = 74 ماه — ارتفاع نمودار ثابت، عرض اسکرول `overflow-x:auto` با اسکرولبار تیره.)

**Verification:** بعد از بیلد، `reviews-dashboard.html` را در preview باز کنید: ستون توزیع 5 بلندترین است؛ نمودار ماهانه اسکرول افقی دارد و بالاترین ماه 2023-07 از دیتا منطبق است.

---

## Task 6: پنل کلیدواژهها

**Objective:** نوارهای افقی پرتکرارترین عبارتها.

**Files:**
- Modify: `scripts/build_reviews_dashboard.py`

**Step 1 (کد):** پنل «کلیدواژههای پرتکرار»: 15 مورد برتر (auto + curated merge، با min count 3) — هر ردیف: کلمه + نوار افقی (عرض نسبی به max) + count monospace. متن فارسی کلمات (باید راستچین شود؛ نوار از راست پر شود — `direction:ltr` برای نوار با `flex-direction:row-reverse` یا scale از راست).

**Verification:** خروجی شامل «تمیز» با count بالای 200 و «استخر» بالای 80 باشد (مطابق بررسی قبلی).

---

## Task 7: جدول کامل نظرات + فیلترها + سورت

**Objective:** جدول حرفهای (استاندارد کاربر) با همهٔ نظرات و فیلترها.

**Files:**
- Modify: `scripts/build_reviews_dashboard.py`

**Step 1 (کد — HTML):** جدول با `thead` sticky (`position:sticky; top:0`)، ستونها:
`# | تاریخ (شمسی) | کاربر | امتیاز (ستاره + عدد) | متن نظر | پاسخ میزبان (دارد/ندارد + آیکون)`
- همه سلولها وسطچین؛ فقط ستون «متن نظر» راستچین (گسترش قانون host-name)
- اعداد انگلیسی monospace `.en`؛ تاریخ با فرمت «۱۴ مرداد ۱۴۰۵» (g2j + نام ماه) + `title` گرگوری
- متنهای طولانی: `max-height + overflow` در سلول + کلیک برای باز/بسته؟ (ساده: کل متن با `line-clamp` ناموجود — بجای آن تمام متن نمایش داده شود، سلول `min-width` مناسب)

**Step 2 (کد — JS):**
- فیلترها: چیپ امتیاز `همه / ≥4.5 / ≥4.8 / فقط 5`؛ چیدمان پاسخ میزبان `همه / دارد / ندارد`؛ چیپ سال شمسی (داینامیک از دیتا)؛ باکس جستجو (عنوان+کاربر+متن)
- سورت: هر ستون sortable — کلیک ۱: ▼ نزولی، کلیک ۲: ▲ صعودی، کلیک ۳: reset به ترتیب پیشفرض (داده)؛ آیکون فلش در header
- شمارش نتایج فیلترشده بالای جدول + empty state «موردی یافت نشد» (با colspan صحیح 6)
- ستون تاریخ: سورت با timestamp گرگوری (نه رشته شمسی)

**Verification (DOM):** در preview:
- سورت امتیاز ▼: ردیف اول یک نظر 5 و آخرین یک نظر 3 (الیاس)
- فیلتر «فقط 5» = 278 ردیف؛ چیپ سال ۱۴۰۵ فقط نظرات سال اخیر
- جستجوی «جاده» حداقل ۱ نتیجه (نظرات مرتضی/علی)
- پاسخ میزبان «ندارد» = 3 ردیف (359−356)

---

## Task 8: فوتور + یادداشت شفافیت + بیلد نهایی وانکوه

**Objective:** تکمیل پایانی برای نسخهٔ وانکوه.

**Files:**
- Modify: `scripts/build_reviews_dashboard.py`

**Step 1 (کد):** فوتور: «داده: {تاریخ} — منبع: api.jajiga.com — {n} نظر از {api_total} (کارت سایت ۴۰۲ — ۴۳ نظر در API موجود نیست)» + دکمهٔ بازنشانی فیلترها.
**Step 2:** بیلد نهایی: `python scripts/build_reviews_dashboard.py --room 3151760`
**Step 3 (تأیید):** `python -c` که `id="revdata"` را از HTML استخراج و `json.loads` کند (اعتبار embed)؛ حجم فایل معقول (< 1MB).

**Verification:** بیلد exit 0؛ JSON embed سالم؛ preview باز و بررسی دیداری؛ شرکت در چت با شواهد.

---

## Task 9: عمومیسازی — تست با کلبه دوم (تالش 3149661)

**Objective:** اثبات اینکه بیلدر برای هر اتاق کار میکند.

**Files:**
- Modify (اختیاری): `scripts/fetch_reviews.py` (اگر خطایی در فچ چند صفحهای دیده شد)
- Test: `data/reviews/3149661_reviews.json`

**Step 1:** `python scripts/fetch_reviews.py 3149661` (327 نظر — 33 صفحه)
**Step 2:** `python scripts/build_reviews_dashboard.py --room 3149661` → `reviews-dashboard.html` بازنویسی میشود (عنوان «کلبه چوبی در تالش - سراگاه»، متا از کش/API جدید)
**Step 3:** تأیید: عنوان، میانگینها، تعداد نظرات (327) و توزیع تغییر میکند؛ هیچ خطای JS در preview.
**Step 4:** بازگشت به وانکوه: بیلد مجدد `--room 3151760` (داشبورد پیشفرض همان وانکوه بماند — `--room` پیشفرض 3151760 ولی اگر آرگومان نداد، آخرین بیلد override میشود؛ تصمیم: پیشفرض همیشه السانکوه مگر `--room` صریح — در کد ثبت شود).

**Verification:** دو بیلد پشتسرهم بدون خطا؛ محتواشان با دادههای متفاوت درست.

---

## Task 10: کامیت

**Objective:** نگهداری پروژه (عادت کاربر: کامیت بعد از هر کار تأییدشده).

**Files:**
- `git add scripts/build_reviews_dashboard.py scripts/fetch_reviews.py data/reviews/ reviews-dashboard.html data/rooms_meta_cache.json`
- پیام: `feat: review-analysis dashboard (وانکوه default, generic room id)`

**Verification:** `git status` تمیز؛ commit در log.

---

## Risks & Mitigations

| ریسک | میتیگیشن |
|---|---|
| API 359 نظر vs کارت 402 | نمایش شفاف هر دو عدد + یادداشت در فوتور |
| متنهای طولانی جدول را خراب میکنند | سلول متن با `min-width` و `overflow-wrap:anywhere`؛ تمام متن نمایش داده شود |
| Persian ZWNJ و کاراکترهای خاص در نظرات | embed از `application/json` + `JSON.parse` (نه template literal) |
| Rate limit در فچ چند اتاق | تأخیر 0.7s بین صفحات و 2-4 بار retry (الان در fetch_reviews.py هست) |
| حجم فایل (359 نظر + متن) | زیر 1MB مطمئن؛ در صورت نیاز lazy-render جدول |
| بدون مدال ردیفهای برتر (سلیقهٔ کاربر) | مستند: ستون امتیاز در ۵ قفل میشود؛ مدال بیمعنی — اگر کاربر خواست اضافه میشود |

## Open Questions
- آیا جدول باید همهٔ 359 ردیف را یکجا قانونگذاری کند یا صفحهبندی داشبورد (۱۰۰تایی)؟ (پیشفرض: همه + رندر سریع؛ در صورت لگ، صفحهبندی)
- خروجی Excel/CSV لازم است؟ (فاز بعد)

---

**Plan ready. Say "go" to start implementation, or tell me what to change.**
