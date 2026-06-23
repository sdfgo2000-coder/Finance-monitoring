#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""특정 날짜 PDF에서 '외국인 유가증권 투자' 섹션 원본 텍스트를 출력해 파싱 오류를 진단.
실행: FSS_AUTH_KEY=xxx TARGET_DATE=2026-05-07 ~/venv/bin/python scripts/dump_pdf_text.py
"""
import os, sys, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fss_monitor as F

auth = os.environ["FSS_AUTH_KEY"]
target = os.environ.get("TARGET_DATE", "2026-05-07")
base = dt.date.fromisoformat(target)
end = base + dt.timedelta(days=3)

posts, seen = [], set()
for cs, ce in F._date_chunks(base, end, 7):
    for p in F.list_daily_posts(auth, cs, ce):
        u = p.get("atchfileUrl")
        if u and u not in seen:
            seen.add(u); posts.append(p)

if not posts:
    print("PDF 없음"); sys.exit(1)

posts.sort(key=lambda p: p.get("regDate", ""))
p = posts[0]
print(f"PDF: {p.get('regDate')} / {p.get('atchfileUrl')}")

text = F.pdf_text(F.download_pdf(p["atchfileUrl"]))

# 외국인 유가증권 투자 섹션만 출력
in_sec = False
for i, ln in enumerate(text.split("\n")):
    s = ln.strip()
    if "외국인" in s and "유가증권 투자" in s:
        in_sec = True
    if in_sec:
        print(f"[{i:04d}] {repr(ln)}")
        if in_sec and i > 0 and "외국인" in s and "유가증권 투자" not in s:
            # 다음 섹션 시작 감지
            pass
        # 50줄 뒤 또는 다음 "====" 구분자 나오면 중단
    if in_sec and i > 200:
        break

print("\n\n=== _pdf_daily_today 결과 ===")
st, bo = F._pdf_daily_today(text)
print(f"주식 당일: {st}, 채권 당일: {bo}")

print("\n=== _pdf_daily_prev 결과 ===")
st_p, bo_p = F._pdf_daily_prev(text)
print(f"주식 전일: {st_p}, 채권 전일: {bo_p}")

d = F._parse_base_date(text)
bd = dt.date.fromisoformat(d)
prev = F._pdf_prev_date(text, bd)
print(f"\n기준일: {d}, 전일: {prev}")
