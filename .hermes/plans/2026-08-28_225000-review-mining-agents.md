# معدن‌کاوی نظرات مهمان‌ها (Review Mining) — پلن اجرا

**Goal:** استخراج همه‌ی نظرات مهمان‌های اتاق‌های جاجیگای مازندران (~۳۴هزار نظر از ۱۴۱۷ اتاق)، دسته‌بندی تماتیک با تیم ایجنت‌ها، و تولید گزارش «مهمان‌ها به چی گله دارن / چی رو دوست دارن» که هیچ میزبانی توی بازار نداره.

**Architecture:** دو خط لوله (pipeline) موازی با زیرعامل‌ها: (۱) جمع‌آوری نظرات به‌صورت shard شده با الگوی موجود fetch_reviews.py + resume-مانیفست، (۲) معدن‌کاوی تماتیک هر shard با تاکسونومی مشترک + داوری کراس-چک، (۳) سنتز گزارش. همه‌ی خروجی‌ها فایل JSON در پروژه؛ ایجنت‌ها فقط خلاصه کوتاه برمی‌گردونن (به‌خاطر سقف خروجی مدل).

**Tech Stack:** Python 3.11 (استاندارد urllib — همون الگوی fetch_reviews.py)، delegate_task (max 10 همزمان)، JSON/SQLite برای کورپوس، Markdown برای گزارش.

**منبع دیتای موجود (تأییدشده):**
- `data/top_rooms_sweep.json` — 2870 اتاق (1417 مازندران، 1352 گیلان)
- سبد نظرات مازندران: 78 اتاق 100+ نظر، 120 اتاق 50-99، 325 اتاق 20-49، 817 اتاق 1-19، 77 اتاق صفر
- `data/reviews/*_reviews.json` — 4 اتاق موجود (858 نظر) → به کورپوس merge می‌شن
- `scripts/fetch_reviews.py` — اسکریپت تست‌شده (api.jajiga.com/api/room/{id}/reviews، per_page=10، sleep 0.7s)

**محدوده (تأیید کاربر 2026-08-28):**
- 1000 اتاق برتر از نظر تعداد نظر، از همه استان‌ها (طبیعتاً مازندران+گیلان غالب، بقیه در صورت حضور) — نه فقط مازندران 20+
- خروجی: گزارش markdown + یک HTML نمایشگر بصری آمار کلی
- تگ‌ها فعلاً به reviews-dashboard.html اضافه نشود

---

## Phase 0 — تصمیم و آماده‌سازی (تکی، بدون ایجنت)

### Task 0.1: تأیید محدوده
کاربر گزینه A/B/C را انتخاب می‌کند. پیش‌فرض: A.

### Task 0.2: ساخت پوشه کاری و تاکسونومی
- Create: `data/reviews_mining/` (شارد‌ها)، `data/reviews_mining/taxonomy.json`
- تاکسونومی مشترک (id + نام فارسی + کلیدواژه‌های کمکی):
  `cleanliness` نظافت‌وبهداشت | `comfort` راحتی‌وتجهیزات (تخت/گرمایش/سرمایش) | `access` دسترسی‌ومسیر | `host` رفتارمیزبان | `expectation_gap` اختلاف‌باتصاویر/انتظار | `noise` نویز‌وهمسایه | `value` قیمت‌و‌ارزش | `nature` طبیعت‌ومحیط | `technical` خرابی‌فنی (آب/برق/اینترنت/کولر) | `other` سایر
- قواعد: هر نظر حداکثر 2 تم، هر ادعا با `review_id` + quote عیناً از متن، نظر خنثی هم داشته باشیم (پرچم `sentiment: pos|neg|neutral`)

**Verify:** `python -c "import json; json.load(open('data/reviews_mining/taxonomy.json'))"` → exit 0

---

## Phase 1 — کاوش API (1 ایجنت)

### Task 1.1: پروب per_page و پیمایش
**Agent:** delegate_task تکی.
**Objective:** چک کند per_page بالاتر (20/50) قبول می‌شود یا نه → تعداد کل درخواست‌ها را کم کند.
**Steps:**
1. برای 3 اتاق نمونه (یکی 100+، یکی 20-49، یکی تازه): `GET api.jajiga.com/api/room/{id}/reviews?page=1&per_page=20` و `per_page=50`
2. چک کند آیا فیلد pagination.total با نمایش کارت اختلاف دارد (طبق درس قبلی ~10٪ کمتر)
3. خروجی: `data/reviews_mining/probe.json` شامل {per_page_optimal, total_vs_card_delta, sample_urls}
**Verify:** probe.json موجود و per_page_optimal ∈ {10,20,50}

### Task 1.2: ساخت مانیفست fetch
اسکریپت `scripts/build_review_manifest.py` (جدید، <150 خط):
- ورودی: top_rooms_sweep.json + انتخاب محدوده + probe.json
- خروجی: `data/reviews_mining/manifest.json` = [{room_id, total_reviews, pages, shard_id}] + خلاصه {total_rooms, total_pages, est_minutes}
- اتاق‌هایی که data/reviews/ already دارند → علامت done
**Verify:** sum(pages) منطقی؛ 4 اتاق موجود done هستند.

---

## Phase 2 — جمع‌آوری موازی (8 ایجنت)

### Task 2.1: شاردبندی و dispatch
- مانیفست را به 8 شارد مساوی (از نظر pages نه اتاق) تقسیم کن
- اسکریپت مشترک `scripts/fetch_reviews_shard.py` (بر پایه fetch_reviews.py، <200 خط):
  - آرگومان: شماره شارد؛ از manifest.json اتاق‌های خودش را می‌خواند
  - state فایل `data/reviews_mining/shard_{N}_state.json` → resume پس از قطعی (اتاق‌های انجام‌شده skip)
  - sleep 1.5s بین صفحه‌ها (10 ایجنت × 0.7 req/s ≈ 5 req/s ایمن)؛ خطای 429 → backoff 30s و کم‌کردن ریتم
  - خروجی هر اتاق: `data/reviews_mining/raw/{room_id}.json` + حذف اتاق از state
- 8 زیرعامل همزمان (batch یک delegate_task با tasks[]، هر کدام: «شارد N را تا تمام شود بگیر؛ خروجی: تعداد اتاق/نظر/خطاها — فقط خلاصه 5 خطی»)

**Verify (من، بعد از batch):**
- `ls data/reviews_mining/raw | wc -l` == اتاق‌های مانیفست
- شمارش کل نظرات ≥ 90٪ تخمین (اختلاف → اتاق‌های جاافتاده fetch مجدد تکی)
- progress report هر 1-2 دقیقه به کاربر (تعداد اتاق/نظر/ETA) طبق عادت گزارش پیشرفت

---

## Phase 3 — merge و داور داده (تکی)

### Task 3.1: ساخت کورپوس
اسکریپت `scripts/build_reviews_corpus.py` (<150 خط):
- merge همه raw/{room_id}.json + 4 فایل قدیمی data/reviews/
- dedupe بر review.id؛ استانداردسازی: {review_id, room_id, village, content, rating, created_at, host_reply}
- خروجی: `data/reviews_mining/corpus.json` (+ ایندکس SQLite اختیاری `reviews_corpus.db` برای کوئری)
**Verify:** شمارش نهایی = مجموع بدون تکرار؛ نمونه‌گیری تصادفی 5 نظر → بازخوانی از raw یکسان.

---

## Phase 4 — معدن‌کاوی تماتیک (5 ایجنت + 1 داور)

### Task 4.1: برچسب‌زنی موازی
- کورپوس به 5 شارد (~6-7K نظر هرکدام) تقسیم می‌شود
- 5 زیرعامل، هر کدام: شارد خودش را می‌خواند، طبق taxonomy.json برچسب می‌زند، خروجی را در `data/reviews_mining/tags_shard_{N}.json` می‌نویسد (فرمت: {review_id, themes[], sentiment, quote_max_140_chars})
- **قانون ضدتوهم:** quote باید عیناً زیررشته‌ای از content باشد — داور چک می‌کند

### Task 4.2: داوری کراس-چک (1 ایجنت)
- 200 نظر نمونه تصادفی از هر 5 شارد: چک quote⊂content، منطقی‌بودن تم نسبت به متن
- خروجی: `data/reviews_mining/judge_report.json` {agreement_rate, violations[]}
- اگر agreement < 85٪ → شارد ضعیف دوباره با پرامپت اصلاح‌شده (فقط شارد خراب)

**Verify:** agreement_rate ≥ 0.85؛ صفر quote ساختگی (هر quote با `q in content` چک اسکریپتی هم می‌شود).

---

## Phase 5 — سنتز و گزارش (1 ایجنت + من)

### Task 5.1: تجمیع آمار
اسکریپت `scripts/summarize_review_themes.py` (<150 خط):
- توزیع تم‌ها (کل، به تفکیک روستا، به تفکیک rating کم/زیاد)، روند سالانه (از created_at — درس microsecond: `slice(0,10)` قبل از parse)، سهم مثبت/منفی هر تم
- خروجی: `data/reviews_mining/theme_stats.json`

### Task 5.2: گزارش فارسی
- گزارش `reports/review-themes-report.md` (فارسی، اعداد انگلیسی، سبک دیتا-محور):
  - رتبه تم‌ها + درصد + 3 quote واقعی از هر تم + کدام روستا در کدام تم ضعیف‌ترین است
  - بخش «درس برای سیدکلا»: چه چیزی مهمان‌ها را عصبانی می‌کند که در لیست ما قابل جبران است
- اختیاری (بعداً): نسخه docx با persian-rtl-docx و اضافه‌کردن تم‌ها به reviews-dashboard.html

**Verify:** هر عدد گزارش با theme_stats.json چک اسکریپتی؛ هر quote با corpus چک شود.

---

## Risks

| ریسک | mitigation |
|---|---|
| Rate-limit جاجیگا با 8 ایجنت همزمان | sleep 1.5s + backoff 429 + کاهش به 4 ایجنت (نیم‌سرعت، ~25 دقیقه) |
| قطعی وسط فچ 90-دقیقه‌ای | state فایل per-shard → resume بدون از دست دادن داده |
| per_page=50 قبول نشود | probe فاز 1 قبل از dispatch؛ برآورد زمان با per_page واقعی |
| توهم ایجنت در برچسب‌زنی | قانون quote⊂content + داور مستقل + چک اسکریپتی نهایی |
| سقف خروجی مدل زیرعامل | ایجنت‌ها فقط به فایل می‌نویسند؛ پیام بازگشتی ≤ 5 خط |
| total کارت ≠ total API (~10٪) | مبنای مانیفست = pagination.total خود API، نه عدد کارت |

## Open Questions
1. محدوده: A (فقط مازندران 20+ نظر) / B (کل مازندران) / C (+ گیلان)؟ — پیش‌فرض A
2. گزارش در همین مرحله markdown کافی است یا docx هم می‌خواهی؟
3. تگ‌های تم بعداً به reviews-dashboard.html هم اضافه شود (فاز جدا)؟

## برآورد زمان
- فاز 0-1: ~10 دقیقه | فاز 2: ~15-25 دقیقه (موازی) | فاز 3: ~5 دقیقه | فاز 4: ~20-30 دقیقه (موازی) | فاز 5: ~15 دقیقه
- جمع: **~1.5 ساعت** با گزارش پیشرفت هر 1-2 دقیقه
