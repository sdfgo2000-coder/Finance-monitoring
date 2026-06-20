#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""이미 수집된 history CSV로 직전 2개월 누적을 주식/채권 분리 검증.
인포맥스 -52.5조가 '주식만'인지 확인.
"""
import os, sys, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fss_monitor as F

hist = F._load_history()
norm = {}
for k, v in hist.items():
    d = k if isinstance(k, str) else k.isoformat()
    norm[d] = v

base = dt.date(2026, 6, 18)
cutoff = F._months_back(base, 2)
print(f"창: {cutoff} ~ {base}")

stock_sum = bond_sum = 0
n = 0
for d in sorted(norm):
    dd = dt.date.fromisoformat(d)
    if cutoff <= dd <= base:
        st, bo = norm[d]
        stock_sum += st
        bond_sum += bo
        n += 1

print(f"영업일 {n}건")
print(f"주식 누적      : {stock_sum:+,}억 = {stock_sum/10000:+.2f}조")
print(f"채권 누적(미감안): {bond_sum:+,}억 = {bond_sum/10000:+.2f}조")
print(f"합계           : {(stock_sum+bond_sum)/10000:+.2f}조")
print()
print(f"→ 인포맥스 -52.5조와 비교: 주식만={stock_sum/10000:+.2f}조")
