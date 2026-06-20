#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ECOS에서 외국인 채권/주식 관련 통계 코드 검색.
실행: ECOS_KEY=xxx ~/venv/bin/python scripts/search_ecos.py
"""
import os, requests

KEY = os.environ["ECOS_KEY"]
BASE = "https://ecos.bok.or.kr/api"

def stat_search(kw):
    url = f"{BASE}/StatisticSearch/{KEY}/json/kr/1/100/{kw}"
    r = requests.get(url, timeout=30)
    data = r.json()
    rows = data.get("StatisticSearch", {}).get("row", [])
    return rows

def stat_list(stat_code):
    url = f"{BASE}/StatisticItemList/{KEY}/json/kr/1/200/{stat_code}"
    r = requests.get(url, timeout=30)
    data = r.json()
    rows = data.get("StatisticItemList", {}).get("row", [])
    return rows

keywords = ["외국인", "외국인채권", "외국인주식", "채권순매수", "외국인투자"]
seen = set()
for kw in keywords:
    rows = stat_search(kw)
    for r in rows:
        code = r.get("STAT_CODE","")
        name = r.get("STAT_NAME","")
        item = r.get("ITEM_NAME1","")
        if code not in seen:
            seen.add(code)
            print(f"[{code}] {name} | {item}")
