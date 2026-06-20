#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""history CSV를 월별로 주식/채권 합산 → PDF 공식 월중 컴럼과 대조.
어느 달/자산의 백필 파싱이 틀렸는지 특정한다.
"""
import os, sys, datetime as dt, collections
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fss_monitor as F

hist = F._load_history()
H = {}
for k, v in hist.items():
    d = k if isinstance(k, str) else k.isoformat()
    H[d] = v

mon = collections.defaultdict(lambda: [0.0, 0.0, 0])  # ym -> [stock, bond, n]
for d in sorted(H):
    st, bo = H[d]
    ym = d[:7]
    mon[ym][0] += st; mon[ym][1] += bo; mon[ym][2] += 1

print(f"{'월':8s} {'주식(조)':>9s} {'채권(조)':>9s} {'일수':>4s}")
for ym in sorted(mon):
    st, bo, n = mon[ym]
    print(f"{ym:8s} {st/10000:+9.1f} {bo/10000:+9.1f} {n:4d}")

print("\n[PDF 공식 월중 컴럼, 6/18 기준]")
print("  5월중: 주식 -48.9  채권 +11.7")
print("  6월중(1~18): 주식 -24.2  채권 +11.2")

print("\n[일별 원시값 — 5월 전체]")
for d in sorted(H):
    if d.startswith("2026-05"):
        st, bo = H[d]
        print(f"  {d}: 주식 {st:+,}억  채권 {bo:+,}억")
