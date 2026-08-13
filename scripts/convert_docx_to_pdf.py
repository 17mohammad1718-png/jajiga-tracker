# -*- coding: utf-8 -*-
"""Convert the cabins docx to PDF via Word COM (preserves table + hyperlinks)."""
import os
import win32com.client

src = r"C:\Users\Ma\Desktop\کلبه های رنج قیمتی من.docx"
out = r"C:\Users\Ma\Desktop\کلبه های رنج قیمتی من.pdf"

word = win32com.client.Dispatch("Word.Application")
word.Visible = False
word.DisplayAlerts = 0
try:
    doc = word.Documents.Open(src, ReadOnly=True)
    doc.SaveAs(out, FileFormat=17)  # 17 = wdFormatPDF
    doc.Close(False)
    print("Saved:", out)
    print("Size:", os.path.getsize(out), "bytes")
finally:
    word.Quit()
