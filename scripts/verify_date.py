#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TARGET_DATE(기본 2026-06-18) 기준 직전 2개월 외인 순매수 누적을 '확정치'로 검증.
윈도우[cutoff, base]보다 며칠 더(base+7일) PDF를 받아, 다음 영업일 PDF의
'전일' 컬럼으로 base일까지 모두 확정치로 교정한 뒤 합산한다.
실행: FSS_AUTH_KEY=xxx TARGET_DATE=2026-06-18 ~/venv/bin/python scripts/verify_date.py
"""
import os, sys, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fss_monitor as F

auth = os.environ["FSS_AUTH_KEY"]
target = os.environ.get("TARGET_DATE", "2026-06-18")
base = dt.date.fromisoformat(target)
cutoff = F._months_back(base, 2)
end = base + dt.timedelta(days=7)          # base 다음 영업일 PDF까지 확보
print(f"윈도우: {cutoff} ~ {base} (확정치 확보용 조회: ~{end})")

# 구간 PDF 목록 (1개월 한도 → 28일 청크)
posts, seen = [], set()
for cs, ce in F._date_chunks(cutoff, end, 28):
    for p in F.list_daily_posts(auth, cs, ce):
        u = p.get("atchfileUrl")
        if u and u not in seen:
            seen.add(u); posts.append(p)
posts.sort(key=lambda p: p.get("regDate", ""))

hist = {}     # 독립 검증용 임시 이력 (운영 CSV 미오염)
for p in posts:
    url = p.get("atchfileUrl")
    if not url:
        continue
    try:
        text = F.pdf_text(F.download_pdf(url))
    except Exception as e:
        print("PDF 실패:", e); continue
    d = F._parse_base_date(text)
    base_d = dt.date.fromisoformat(d)
    # 전일 확정치 (헤더 실제 전일 날짜로)
    prev_date = F._pdf_prev_date(text, base_d)
    st_prev, bo_prev = F._pdf_daily_prev(text)
    if prev_date and st_prev is not None and bo_prev is not None:
        hist[prev_date.isoformat()] = (st_prev, bo_prev)
    # 당일 잠정치 (다음날 PDF가 확정치로 덮음)
    st, bo = F._pdf_daily_today(text)
    if st is not None and bo is not None:
        hist[d] = (st, bo)

# 윈도우 합산
stock_sum = bond_sum = 0; n = 0
for d in sorted(hist):
    dd = dt.date.fromisoformat(d)
    if cutoff <= dd <= base:
        st, bo = hist[d]
        stock_sum += st; bond_sum += bo; n += 1

total = (stock_sum + bond_sum) / 10000
print(f"\n=== {target} 확정치 검증 ===")
print(f"영업일 {n}건")
print(f"주식 누적: {stock_sum:+,}억 = {stock_sum/10000:+.2f}조")
print(f"채권 누적: {bond_sum:+,}억 = {bond_sum/10000:+.2f}조")
print(f">>> 직전 2개월 누적(확정치) = {total:+.2f}조 (인포맥스 참고: -52.5조)")
