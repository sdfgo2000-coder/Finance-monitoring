#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""과거 5월 PDF들의 채권 행 원문 + 토큰 파싱을 한 번에 덤프.
_daily_col이 어느 컴럼을 집는지, 레이아웃이 6/18과 다른지 확인.
"""
import os, sys, re, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fss_monitor as F

auth = os.environ["FSS_AUTH_KEY"]
posts = []
seen = set()
for cs, ce in F._date_chunks(dt.date(2026,5,15), dt.date(2026,5,22), 28):
    for p in F.list_daily_posts(auth, cs, ce):
        u = p.get("atchfileUrl")
        if u and u not in seen:
            seen.add(u); posts.append(p)

for p in posts:
    url = p.get("atchfileUrl")
    try:
        text = F.pdf_text(F.download_pdf(url))
    except Exception as e:
        print("PDF 실패:", e); continue
    base = F._parse_base_date(text)
    print(f"\n===== {base} =====")
    fixed = re.sub(r"(\d)\s+,", r"\1,", text)
    in_sec = False
    for ln in fixed.split("\n"):
        s = ln.strip()
        if "외국인" in s and "유가증권 투자" in s:
            in_sec = True
        if in_sec:
            if s.startswith("순매수") or s.startswith("채권") or "만기상환" in s or "국채선물" in s:
                print("  RAW:", repr(s))
                ints = []
                for t in s.split():
                    if "." in t or "(" in t or "%" in t: continue
                    c = t.replace(",", "")
                    if re.fullmatch(r"[+-]?\d+", c): ints.append(int(c))
                print("       ints:", ints, "→ _daily_col(억):", F._daily_col(s))
            if "국채선물" in s: break
    print("  _pdf_daily_today:", F._pdf_daily_today(text))
