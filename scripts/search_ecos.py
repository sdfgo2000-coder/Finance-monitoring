#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ECOS 채권보유표 항목 상세 + 외국인 관련 코드 실제 데이터 조회."""
import os, requests

KEY = os.environ["ECOS_KEY"]
BASE = "https://ecos.bok.or.kr/api"

def item_list(stat_code):
    url = f"{BASE}/StatisticItemList/{KEY}/json/kr/1/300/{stat_code}"
    r = requests.get(url, timeout=30)
    return r.json().get("StatisticItemList", {}).get("row", [])

def fetch(stat_code, item_code, start="20260401", end="20260618", period="D"):
    url = (f"{BASE}/StatisticSearch/{KEY}/json/kr/1/100/"
           f"{stat_code}/{period}/{start}/{end}/{item_code}")
    r = requests.get(url, timeout=30)
    data = r.json()
    rows = data.get("StatisticSearch", {}).get("row", [])
    if not rows:
        print("  → 데이터 없음:", str(data)[:200])
    return rows

# 채권보유표 항목 탐색
print("=== 채권보유표(0000000805) 항목 ===")
for row in item_list("0000000805"):
    name = " / ".join(filter(None, [row.get(f"ITEM_NAME{i}") for i in range(1,5)]))
    print(f"  [{row.get('ITEM_CODE')}] {name}")

# 282Y006 채권발행-보유관계표 항목 탐색
print("\n=== 채권발행-보유관계표(282Y006) 항목 ===")
for row in item_list("282Y006"):
    name = " / ".join(filter(None, [row.get(f"ITEM_NAME{i}") for i in range(1,5)]))
    print(f"  [{row.get('ITEM_CODE')}] {name}")
