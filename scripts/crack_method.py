#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""인포맥스 표(6/4~6/18, 직전2개월 누적, 조원)와 모든 계산법을 자동 대조.
어떤 윈도우/구성이 표와 일치하는지 오차 기준으로 찾아낸다.
추가 데이터/추측 불필요 — 이미 수집된 history CSV만으로 결론.
"""
import os, sys, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fss_monitor as F

# ── 인포맥스 정답표 (조원) ──
TARGET = {
    "2026-06-04": -38.6, "2026-06-05": -43.0, "2026-06-08": -45.7,
    "2026-06-09": -49.2, "2026-06-10": -50.7, "2026-06-11": -60.6,
    "2026-06-12": -61.4, "2026-06-15": -57.8, "2026-06-16": -56.3,
    "2026-06-17": -52.1, "2026-06-18": -52.5,
}

hist = F._load_history()
H = {}
for k, v in hist.items():
    d = k if isinstance(k, str) else k.isoformat()
    H[d] = v   # (stock억, bond억)

days = sorted(H)
print(f"보유 데이터: {days[0]} ~ {days[-1]} ({len(days)}건)\n")

def daily(d, mode):
    st, bo = H.get(d, (0, 0))
    if mode == "stock": return st
    if mode == "both":  return st + bo
    if mode == "bond":  return bo

def window_sum(base, start, mode):
    s = 0.0
    for d in days:
        dd = dt.date.fromisoformat(d)
        if start <= dd <= base:
            s += daily(d, mode)
    return s

def err(series):
    diffs = []
    for k, tgt in TARGET.items():
        if k in series:
            diffs.append(abs(series[k] - tgt))
    return (sum(diffs)/len(diffs) if diffs else 999), len(diffs)

results = []

# 가설 A: rolling 2개월 (start = base 2개월전 + offset일)
for mode in ("stock", "both"):
    for off in range(-20, 21):
        series = {}
        for k in TARGET:
            base = dt.date.fromisoformat(k)
            start = F._months_back(base, 2) + dt.timedelta(days=off)
            series[k] = window_sum(base, start, mode)/10000
        e, n = err(series)
        if n == len(TARGET):
            results.append((e, f"rolling2m {mode:5s} offset{off:+d}일", series))

# 가설 B: 역월 (전월 1일 ~ base) + base 시프트
for mode in ("stock", "both"):
    for bshift in range(-3, 4):
        series = {}
        for k in TARGET:
            base = dt.date.fromisoformat(k) + dt.timedelta(days=bshift)
            first = dt.date(base.year, base.month, 1)
            pm = (first - dt.timedelta(days=1)).replace(day=1)
            series[k] = window_sum(base, pm, mode)/10000
        e, n = err(series)
        if n == len(TARGET):
            results.append((e, f"역월(전월1일~) {mode:5s} bshift{bshift:+d}", series))

# 가설 C: 고정 일수 N일 윈도우
for mode in ("stock", "both"):
    for N in range(40, 75):
        series = {}
        for k in TARGET:
            base = dt.date.fromisoformat(k)
            start = base - dt.timedelta(days=N)
            series[k] = window_sum(base, start, mode)/10000
        e, n = err(series)
        if n == len(TARGET):
            results.append((e, f"고정{N}일 {mode:5s}", series))

results.sort(key=lambda x: x[0])
print("=== 오차 작은 순 상위 8개 ===")
for e, name, series in results[:8]:
    print(f"  MAE={e:5.2f}조  {name}")

print("\n=== 최적 가설 상세 vs 인포맥스 ===")
best = results[0]
print(f"방식: {best[1]}  (MAE={best[0]:.2f}조)")
print(f"{'날짜':12s} {'계산':>8s} {'인포맥스':>8s} {'차이':>7s}")
for k in sorted(TARGET):
    c = best[2][k]; t = TARGET[k]
    print(f"{k:12s} {c:+8.1f} {t:+8.1f} {c-t:+7.1f}")
