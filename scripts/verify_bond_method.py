#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""채권 누적을 두 방식으로 비교해 인포맥스(-52.5조) 갭의 원인을 특정.
  (A) 순매수 컬럼   = 매수-매도 (만기상환 미감안)  ← 현재 코드
  (B) 잔액 일변화   = 매수-매도-만기상환 (만기상환 감안) ← 인포맥스 공식
주식은 동일. 윈도우[cutoff, base]에서 각각 합산해 합계를 비교한다.
실행: FSS_AUTH_KEY=xxx TARGET_DATE=2026-06-18 ~/venv/bin/python scripts/verify_bond_method.py
"""
import os, sys, re, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fss_monitor as F

auth = os.environ["FSS_AUTH_KEY"]
target = os.environ.get("TARGET_DATE", "2026-06-18")
base = dt.date.fromisoformat(target)
cutoff = F._months_back(base, 2)
end = base + dt.timedelta(days=7)
print(f"윈도우: {cutoff} ~ {base} (조회 ~{end})")

def parse_row(text):
    """(주식 당일·전일, 채권순매수 당일·전일, 채권잔액 당일·전일) 반환."""
    fx = re.sub(r"(\d)\s+,", r"\1,", text)
    st_t = st_p = bo_t = bo_p = bz_t = bz_p = None
    in_sec = False
    for ln in fx.split("\n"):
        s = ln.strip()
        if "외국인" in s and "유가증권 투자" in s:
            in_sec = True; continue
        if not in_sec: continue
        if st_t is None and s.startswith("합계"):
            st_t = F._daily_col(s); st_p = F._prev_col(s)
        if bo_t is None and s.startswith("순매수") and "만기상환" in s:
            bo_t = F._daily_col(s); bo_p = F._prev_col(s)
            ints = []
            for t in s.split():
                if "." in t or "(" in t or "%" in t: continue
                c = t.replace(",", "")
                if re.fullmatch(r"[+-]?\d+", c): ints.append(int(c))
            if len(ints) >= 3:
                bz_t = ints[-1]          # 당일 잔액
                # 전일 잔액은 별도 컬럼이 없어 None (잔액은 당일만 신뢰)
    return st_t, st_p, bo_t, bo_p, bz_t

# 구간 PDF 수집
posts, seen = [], set()
for cs, ce in F._date_chunks(cutoff, end, 28):
    for p in F.list_daily_posts(auth, cs, ce):
        u = p.get("atchfileUrl")
        if u and u not in seen:
            seen.add(u); posts.append(p)
posts.sort(key=lambda p: p.get("regDate", ""))

stock = {}     # date -> 주식 순매수(확정 우선)
bond_buy = {}  # date -> 채권 순매수(만기상환 미감안)
balance = {}   # date -> 채권 잔액
for p in posts:
    url = p.get("atchfileUrl")
    if not url: continue
    try:
        text = F.pdf_text(F.download_pdf(url))
    except Exception as e:
        print("PDF 실패:", e); continue
    d = F._parse_base_date(text)
    bd = dt.date.fromisoformat(d)
    st_t, st_p, bo_t, bo_p, bz_t = parse_row(text)
    prev_date = F._pdf_prev_date(text, bd)
    # 전일 확정치
    if prev_date and st_p is not None: stock[prev_date.isoformat()] = st_p
    if prev_date and bo_p is not None: bond_buy[prev_date.isoformat()] = bo_p
    # 당일 잠정치(확정치가 있으면 덮어쓰지 않게 setdefault식 처리)
    if st_t is not None: stock.setdefault(d, st_t)
    if bo_t is not None: bond_buy.setdefault(d, bo_t)
    if bz_t is not None: balance[d] = bz_t

# 잔액 일변화 = 채권 순투자(만기상환 감안)
bdates = sorted(balance)
bond_net = {}   # date -> 잔액변화
for i in range(1, len(bdates)):
    d0, d1 = bdates[i-1], bdates[i]
    bond_net[d1] = balance[d1] - balance[d0]

def wsum(dmap):
    tot = n = 0
    for d, v in dmap.items():
        dd = dt.date.fromisoformat(d)
        if cutoff <= dd <= base:
            tot += v; n += 1
    return tot, n

st_sum, st_n = wsum(stock)
boA_sum, boA_n = wsum(bond_buy)   # 순매수
boB_sum, boB_n = wsum(bond_net)   # 잔액변화(만기상환 감안)

print(f"\n주식 누적           : {st_sum/10000:+.2f}조 ({st_n}일)")
print(f"채권(A 순매수,미감안) : {boA_sum/10000:+.2f}조 ({boA_n}일)")
print(f"채권(B 잔액변화,감안) : {boB_sum/10000:+.2f}조 ({boB_n}일)")
print(f"만기상환 추정(A-B)   : {(boA_sum-boB_sum)/10000:+.2f}조")
print()
print(f"합계 A (현재 방식)   : {(st_sum+boA_sum)/10000:+.2f}조")
print(f"합계 B (만기상환 감안): {(st_sum+boB_sum)/10000:+.2f}조")
print(f"→ 인포맥스 참고      : -52.5조")
