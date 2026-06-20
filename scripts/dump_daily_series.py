#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""4월초~기준일 전체 일별 외인 순매수(주식·채권) 시계열을 한 번에 덤프.
인포맥스 화면(3304/4257) 일별값과 직접 대조해 어느 날이 튀는지 특정한다.
또한 각 영업일의 '직전 2개월 롤링 누적'도 함께 출력해 인포맥스 일별 누적과 비교.
실행: FSS_AUTH_KEY=xxx ~/venv/bin/python scripts/dump_daily_series.py
"""
import os, sys, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fss_monitor as F

auth = os.environ["FSS_AUTH_KEY"]
start = dt.date(2026, 3, 25)     # 4/4 윈도우 시작 커버용 여유
end   = dt.date(2026, 6, 25)
print(f"수집: {start} ~ {end}")

posts, seen = [], set()
for cs, ce in F._date_chunks(start, end, 28):
    for p in F.list_daily_posts(auth, cs, ce):
        u = p.get("atchfileUrl")
        if u and u not in seen:
            seen.add(u); posts.append(p)
posts.sort(key=lambda p: p.get("regDate", ""))

stock, bond = {}, {}
for p in posts:
    url = p.get("atchfileUrl")
    if not url: continue
    try:
        text = F.pdf_text(F.download_pdf(url))
    except Exception as e:
        print("PDF 실패:", e); continue
    d = F._parse_base_date(text)
    bd = dt.date.fromisoformat(d)
    st_t, bo_t = F._pdf_daily_today(text)
    st_p, bo_p = F._pdf_daily_prev(text)
    prev_date = F._pdf_prev_date(text, bd)
    if prev_date and st_p is not None: stock[prev_date.isoformat()] = st_p   # 확정 우선
    if prev_date and bo_p is not None: bond[prev_date.isoformat()] = bo_p
    if st_t is not None: stock.setdefault(d, st_t)
    if bo_t is not None: bond.setdefault(d, bo_t)

print("\n[일별 순매수 — 억원] (주식 / 채권 / 합계)")
for d in sorted(stock):
    st = stock.get(d, 0); bo = bond.get(d, 0)
    print(f"  {d}: 주식 {st:+,}  채권 {bo:+,}  합계 {st+bo:+,}")

print("\n[직전 2개월 롤링 누적 — 조원] (인포맥스 대조용)")
ref = {"2026-06-04": -38.6, "2026-06-18": -52.5}
for base in sorted(stock):
    bd = dt.date.fromisoformat(base)
    cut = F._months_back(bd, 2)
    tot = n = 0
    for d in stock:
        dd = dt.date.fromisoformat(d)
        if cut <= dd <= bd:
            tot += stock.get(d, 0) + bond.get(d, 0); n += 1
    mark = f"   ← 인포맥스 {ref[base]:+.1f}" if base in ref else ""
    print(f"  {base} ({cut}~): {tot/10000:+.2f}조 ({n}일){mark}")
