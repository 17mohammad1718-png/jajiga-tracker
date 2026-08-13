# -*- coding: utf-8 -*-
"""Build PDF: cabins in my price range, title cells = hyperlinks. RTL Persian, Vazir."""
import json
import re

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle)

MY_PRICE = 2750000
LO, HI = int(MY_PRICE * 0.75), int(MY_PRICE * 1.25)
MY_ID = 3297585
BASE = "https://www.jajiga.com/room/"

FONT = r"C:\Users\Ma\Vazir_extracted\Vazir-Regular.ttf"
FONT_BOLD = r"C:\Users\Ma\Vazir_extracted\Vazir-Bold.ttf"
pdfmetrics.registerFont(TTFont("Vazir", FONT))
pdfmetrics.registerFont(TTFont("Vazir-Bold", FONT_BOLD))


def rt(s):
    """RTL-transform a Persian string for ReportLab."""
    return get_display(arabic_reshaper.reshape(s))


def fmt(n):
    return f"{n:,}"


with open("data/pricing/pricing-dataset.json", encoding="utf-8") as f:
    cabins = json.load(f)

in_range = [c for c in cabins if LO <= c["min_price"] <= HI]
in_range.sort(key=lambda c: c["min_price"])


def village_from_title(title):
    m = re.search(r"بابلکنار\s*-\s*([^\s-]+)", title)
    return m.group(1) if m else "—"


# Styles
title_st = ParagraphStyle("title", fontName="Vazir-Bold", fontSize=15,
                          leading=22, alignment=1, textColor=colors.HexColor("#1F3864"))
sub_st = ParagraphStyle("sub", fontName="Vazir", fontSize=9.5, leading=14,
                        alignment=1, textColor=colors.HexColor("#555555"))
head_st = ParagraphStyle("head", fontName="Vazir-Bold", fontSize=9.5, leading=13,
                         alignment=1, textColor=colors.HexColor("#1F3864"))
cell_st = ParagraphStyle("cell", fontName="Vazir", fontSize=9, leading=12,
                         alignment=1)
link_st = ParagraphStyle("link", parent=cell_st, textColor=colors.HexColor("#0563C1"))

headers = ["ردیف", "عنوان کلبه (لینک)", "قیمت (تومان)", "مساحت (م²)", "خواب", "نفرات", "روستا"]
col_widths = [1.0 * cm, 6.2 * cm, 2.6 * cm, 2.0 * cm, 1.3 * cm, 1.7 * cm, 1.9 * cm]

data = [[Paragraph(rt(h), head_st) for h in headers]]
for idx, c in enumerate(in_range, 1):
    title = c["title"]
    url = BASE + str(c["id"])
    if c["id"] == MY_ID:
        title += " ★ (شما)"
    link_text = f'<a href="{url}" color="#0563C1"><u>{rt(title)}</u></a>'
    row = [
        Paragraph(rt(str(idx)), cell_st),
        Paragraph(link_text, link_st),
        Paragraph(rt(fmt(c["min_price"])), cell_st),
        Paragraph(rt(str(c.get("floor_area") or "—")), cell_st),
        Paragraph(rt(str(c.get("bedrooms") or "—")), cell_st),
        Paragraph(rt(f"{c.get('guest_number') or '—'}-{c.get('max_guest_number') or '—'}"), cell_st),
        Paragraph(rt(village_from_title(title)), cell_st),
    ]
    data.append(row)

table = Table(data, colWidths=col_widths, repeatRows=1)
table.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9E2F3")),
    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#8FAADC")),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 3),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1),
     [colors.white, colors.HexColor("#F2F6FC")]),
]))

out = r"C:\Users\Ma\Desktop\کلبه های رنج قیمتی من.pdf"
doc = SimpleDocTemplate(out, pagesize=A4,
                        leftMargin=2.0 * cm, rightMargin=2.0 * cm,
                        topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                        title="کلبه‌های رنج قیمتی من")
story = [
    Paragraph(rt(f"کلبه‌های رنج قیمتی من — {fmt(LO)} تا {fmt(HI)} تومان"), title_st),
    Spacer(1, 4),
    Paragraph(rt(f"({len(in_range)} کلبه در محدوده ±۲۵٪ قیمت کلبه سوئیسی سیدکلا — ۲,۷۵۰,۰۰۰ تومان)"), sub_st),
    Spacer(1, 10),
    table,
]
doc.build(story)
print("Saved:", out)

import os
print("Size:", os.path.getsize(out), "bytes")
