#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""채권 잔액 일변화 = 채권 순투자(만기상환 감안) 검증.
6/17, 6/18 PDF를 각각 내려받아:
  - 주식 합계 당일
  - 채권 순매수(만기상환 미감안) 당일
  - 채권 잔액
을 출력한 뒤 6/18 잔액 - 6/17 잔액을 계산한다.

실행: FSS_AUTH_KEY=xxx ~/venv/bin/python scripts/verify_잔액.py
"""
import os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fss_monitor as F
import datetime as dt

auth_key = os.environ["FSS_AUTH_KEY"]
KST = F.KST

def parse_row(text):
    """주식합계 당일, 채권 순매수(미감안) 당일, 채권 잔액 반환."""
    text_fixed = re.sub(r"(\d)\s+,", r"\1,", text)

    stock = bond_daily = bond_잔액 = None
    in_sec = False
    for ln in text_fixed.split("\n"):
        s = ln.strip()
        if "외국인" in s and "유가증권 투자" in s:
            in_sec = True; continue
        if not in_sec: continue

        if stock is None and s.startswith("합계"):
            stock = F._daily_col(s)

        if bond_daily is None and s.startswith("순매수") and "만기상환" in s:
            bond_daily = F._daily_col(s)
            ints = []
            for t in s.split():
                if "." in t or "(" in t or "%" in t: continue
                c = t.replace(",", "")
                if re.fullmatch(r"[+-]?\d+", c):
                    ints.append(int(c))
            if ints:
                bond_잔액 = ints[-1]

        if stock is not None and bond_daily is not None and bond_잔액 is not None:
            break
    return stock, bond_daily, bond_잔액

today = dt.datetime.now(KST).date()
posts = F.list_daily_posts(auth_key, today - dt.timedelta(days=10), today)
posts.sort(key=lambda x: x.get("regDate",""))

results = {}
seen = set()
for p in posts:
    url = p.get("atchfileUrl")
    if not url or url in seen: continue
    seen.add(url)
    try:
        text = F.pdf_text(F.download_pdf(url))
    except Exception as e:
        print(f"PDF 실패: {e}"); continue
    base = F._parse_base_date(text)
    st, bd, bz = parse_row(text)
    results[base] = (st, bd, bz)
    print(f"[{base}] 주식당일={st:+,}억  채권당일(미감안)={bd:+,}억  채권잔액={bz:,}억")

dates = sorted(results.keys())
print()
for i in range(1, len(dates)):
    d0, d1 = dates[i-1], dates[i]
    _, _, z0 = results[d0]
    st1, bd1, z1 = results[d1]
    if z0 and z1:
        bond_감안 = z1 - z0
        total = st1 + bond_감안
        print(f"=== {d0} → {d1} ===")
        print(f"  주식 당일         : {st1:+,}억")
        print(f"  채권 순투자(감안) : {bond_감안:+,}억  (잔액 {z1:,} - {z0:,})")
        print(f"  채권 순매수(미감안): {bd1:+,}억")
        print(f"  일별 합계(감안)   : {total:+,}억 = {total/10000:+.4f}조")
