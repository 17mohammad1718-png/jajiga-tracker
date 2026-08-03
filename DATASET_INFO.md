# Jajiga Tracker — Complete Dataset

`jajiga_complete_dataset.json` — یک فایل JSON واحد شامل **تمام دیتاهای پروژه jajiga-tracker** بدون هیچ حذف یا تغییری، برای خوندن بهینه توسط هوش مصنوعی.

## ساختار فایل

| کلید | محتوا | حجم تقریبی |
|---|---|---|
| `meta` | توضیح ساختار، زمان تولید، شمارندههای کامل (counts) | — |
| `hosts_db` | کل فایل `data/hosts-babolkenar.json` — ۳۴۶ میزبان با پروفایل کامل + اتاقهایشان | 428 KB |
| `all_cabins` | کل فایل `data/all-cabins.json` — ۱۵۷ کلبه در ۶ روستا با occupancy | 120 KB |
| `supply` | کل فایل `data/supply-data.json` — تایملاین عرضه (۳۴۶ میزبان / ۴۶۷ اتاق / ۶۸ ماه / آمار روستاها) | 276 KB |
| `room_dates` | کل فایل `data/supply/room-dates.json` — تاریخ اولین عکس/نظر/ورود برای ۴۶۷ اتاق | 160 KB |
| `snapshots` | همه فایلهای `data/snapshots/*.json` — عکسهای نقطهای تاریخ عرضه | 11 KB |
| `pricing.json` | `data/pricing/pricing-dataset.json` — ۱۰۸ کلبه / ۴ روستا با تمام فاکتورها | 368 KB |
| `pricing.csv` | `data/pricing/pricing-dataset.csv` — همان ۱۰۸ ردیف بهصورت dict | 92 KB |
| `raw_pricing` | همه دامپهای خام API برای ۵ دایرکتوری (۱۱۸ فایل) — **کاملترین داده** با provenance | ~1.9 MB |

## نکات

- **صفر از دستدادن داده:** هر منبع بهصورت verbatim (بدون تغییر فیلد) داخل فایل قرار گرفته.
- در `raw_pricing` هر رکورد یک wrapper دارد: `{village_raw_dir, source_file, room_id, data}` — فیلد `data` دقیقاً پاسخ خام `/api/room/{id}` است.
- اعداد همهانگلیسی، متن فارسی حفظ شده، `ensure_ascii=False` → یونیکد واقعی.
- `meta.structure_guide` راهنمای خواندن برای AI است؛ `meta.counts` خلاصه اعداد.

## اجرا

```bash
python scripts/aggregate_jajiga_dataset.py   # ساخت فایل
python scripts/verify_aggregation.py         # تأیید بدون اتلاف (exit 0 = OK)
```

> ⚠️ اگر snapshot جدیدی توسط cron ساخته شد، اسکریپت aggregation را دوباره اجرا کنید تا شاملش شود.
