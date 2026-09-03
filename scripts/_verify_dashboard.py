#!/usr/bin/env python3
import re, json

with open(r"H:\projects\jajiga-tracker\داشبورد-تخمین-درآمد.html", encoding="utf-8") as f:
    c = f.read()

# 1. چک کنیم بخش realized هست
print("REALIZED block in HTML:", "درآمد محقق‌شده" in c)
print("realized table tbody:", 'id="rtbody"' in c)
print("RK var defined:", "const RK =" in c)

# 2. استخراج داده REALIZED
m = re.search(r"const REALIZED = (\[.*?\]);", c, re.DOTALL)
if m:
    data = json.loads(m.group(1))
    print(f"REALIZED rooms: {len(data)}")
    if data:
        top = data[0]
        print(f"Top room: {top['title']} | nights: {len(top.get('nights', []))} | net: {top['net']:,}")
        for n in top.get('nights', [])[:3]:
            print(f"  {n['date']}: {n['price']:,} disc={n['discount']}")

# 3. چک کنیم تگ‌های script و html بسته شدند
print("\nHTML structure:")
print("DOCTYPE:", c.strip().startswith("<!DOCTYPE html>"))
print("</html> at end:", c.strip().endswith("</html>"))
print("</script> count:", c.count("</script>"))
print("<script> count:", c.count("<script>"))
