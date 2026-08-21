# پلن اصلاح خط جداکننده هفته و ماه در تقویم رادار رقبا

> **Goal:** رفع جابه‌جایی یک‌روزه خطوط عمودی جداکننده هفته (wb) و ماه (mb) در جدول تقویم «داشبورد رادار رقبا».
>
> **علت ریشه‌ای:** داکیومنت `dir='rtl'` است و روزهای تقویم راست‌به‌چپ چیده می‌شوند (اولین روز سمت راست، روزهای بعدی به سمت چپ). خط‌های جداکننده با `border-left` روی سلولِ شروع هفته (شنبه) و شروع ماه زده می‌شوند، ولی در چیدمان RTL مرز واقعی هفته/ماه، **لبه راستِ** سلولِ شروع است نه چپش. نتیجه: خط یک روز دیرتر (بین شنبه و یکشنبه / بین روز اول و دوم ماه جدید) می‌افتد — همان چیزی که کاربر «یک روز زیادی جلو» می‌بیند.

## فایل‌هایی که تغییر می‌کنند

- **Modify:** `C:\Users\Ma\projects\jajiga-tracker\scripts\build_radar_dashboard.py` (خطوط ۱۱۴۶–۱۱۵۱، بلوک CSS قالب)
- **Regenerate:** `C:\Users\Ma\projects\jajiga-tracker\competitor-radar.html` (خروجی اسکریپت — دست‌کاری مستقیم نمی‌شود)

## مراحل

### گام ۱ — اصلاح ۴ قانون CSS در build_radar_dashboard.py

در قالب CSS (خطوط ۱۱۴۶–۱۱۵۱) ۴ قانون را از `border-left` به `border-right` تغییر بده:

| قبل | بعد |
|---|---|
| `.cal td.c.wb {{ border-left:2px solid #4a729c; background-image:linear-gradient(90deg, rgba(74,114,156,.16), rgba(74,114,156,0) 70%); }}` | `.cal td.c.wb {{ border-right:2px solid #4a729c; background-image:linear-gradient(270deg, rgba(74,114,156,.16), rgba(74,114,156,0) 70%); }}` |
| `.cal td.c.mb {{ border-left:3px solid #3f7cc4; }}` | `.cal td.c.mb {{ border-right:3px solid #3f7cc4; }}` |
| `.cal th.dayh.wb {{ border-left:2px solid #4a729c; }}` | `.cal th.dayh.wb {{ border-right:2px solid #4a729c; }}` |
| `.cal th.dayh.mb {{ border-left:3px solid #3f7cc4; }}` | `.cal th.dayh.mb {{ border-right:3px solid #3f7cc4; }}` |

> گرادیانت `90deg → 270deg` فقط برای این که هایلایت آبی همچنان از خطِ جداکننده به سمت داخل سلول محو شود (ظاهری؛ اگر نزنیم چیزی نمی‌شکند).

توضیح منطق: این کلاس‌ها هم در تقویم آینده (`col_extras`) و هم در تب «گذشته» (`past_th_for` و سلول‌هایش) استفاده می‌شوند؛ یک تغییر CSS همه‌جا را درست می‌کند.

### گام ۲ — بازسازی داشبورد

```
cd C:\Users\Ma\projects\jajiga-tracker
python scripts/build_radar_dashboard.py
```

خروجی مورد انتظار: `Wrote .../competitor-radar.html (... bytes) | N rooms | N day columns`

### گام ۳ — بازرسی

1. **grep در خروجی:** مطمئن شو ۴ قانون در `competitor-radar.html` با `border-right` نوشته شده‌اند:
   ```
   grep -n "cal td.c.wb\|cal td.c.mb\|cal th.dayh.wb\|cal th.dayh.mb" competitor-radar.html
   ```
2. **چک بصری در پیش‌نمایش:** باز کردن داشبورد → تب «تقویم»:
   - خط هفته باید دقیقاً بین **جمعه | شنبه** باشد (و دیگر بین شنبه و یکشنبه نه).
   - خط ماه باید روی **روز اول ماه جدید** باشد (بین آخرین روز ماه قبل و روز اول ماه بعد).
   - تب «گذشته» هم باید خط هفته را در جای درست نشان بدهد.

## ریسک‌ها / نکات

- اگر اولین ستون تقویم (دیروز) مصادف با شنبه باشد، خطِ `border-right` بین ستون نام اتاق و اولین روز می‌افتد — این درست است (آغاز هفته).
- کلاس `mb` فقط روی تقویم آینده می‌آید (تب گذشته خط ماه ندارد)؛ همین CSS کافی است.
- کرون روزانه رادار (`radar_daily.py` در `~/AppData/Local/hermes/scripts/`) از همین اسکریپت استفاده می‌کند؛ پس اصلاح، دائمی است و با هر بازسازی باقی می‌ماند.
- **تغییر دیگری نمی‌خواهد** — فقط همین ۴ خط CSS + بازسازی.
