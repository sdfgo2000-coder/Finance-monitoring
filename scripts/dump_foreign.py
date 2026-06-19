#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""외국인 유가증권 투자 표 원시 라인 덤프(진단용).
실행: ~/venv/bin/python scripts/dump_foreign.py
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fss_monitor as F

url, reg = F.fetch_daily_pdf_url(os.environ["FSS_AUTH_KEY"])
print("PDF:", url, "| 게시:", reg)
text = F.pdf_text(F.download_pdf(url))

in_sec = False
print("=" * 70)
for ln in text.split("\n"):
    s = ln.strip()
    if "외국인" in s and "유가증권 투자" in s:
        in_sec = True
    if in_sec:
        print(repr(s))
        # 채권 표 끝(다음 큰 섹션) 만나면 종료
        if s.startswith("순매수") and "만기상환" in s:
            # 만기상환 라인의 토큰 분해 출력
            print("  └ tokens:", s.split())
        if s.startswith("◇") or s.startswith("□") or ("외환" in s and "동향" in s):
            break
print("=" * 70)
print("[_pdf_daily_today] =>", F._pdf_daily_today(text))
