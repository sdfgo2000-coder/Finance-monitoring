#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TARGET_DATE(기본 2026-06-18) 기준 직전 2개월 외인 순매수 누적을 검증.
해당 날짜의 PDF를 받아 compute_foreign_2m()를 그 기준일로 호출한다.
실행: FSS_AUTH_KEY=xxx TARGET_DATE=2026-06-18 ~/venv/bin/python scripts/verify_date.py
"""
import os, sys, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fss_monitor as F

auth = os.environ["FSS_AUTH_KEY"]
target = os.environ.get("TARGET_DATE", "2026-06-18")
tgt = dt.date.fromisoformat(target)

# 해당 날짜 게시물(PDF) 찾기
posts = F.list_daily_posts(auth, tgt - dt.timedelta(days=7), tgt + dt.timedelta(days=2))
posts.sort(key=lambda p: p.get("regDate", ""))

text = None
for p in posts:
    url = p.get("atchfileUrl")
    if not url:
        continue
    try:
        t = F.pdf_text(F.download_pdf(url))
    except Exception as e:
        print("PDF 실패:", e); continue
    if F._parse_base_date(t) == target:
        text = t
        break

if text is None:
    print(f"[ERROR] {target} PDF를 찾지 못함")
    sys.exit(1)

st, bo = F._pdf_daily_today(text)
print(f"=== {target} 검증 ===")
print(f"PDF 당일 주식 {st:+,}억 · 채권 {bo:+,}억")
res = F.compute_foreign_2m(text, target, auth_key=auth)
print(f"\n>>> 직전 2개월 누적 = {res:+.2f}조 (인포맥스 참고: -52.5조)")
