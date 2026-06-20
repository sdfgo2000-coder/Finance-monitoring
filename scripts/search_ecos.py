#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ECOS 통계목록 전체 조회 후 외국인 관련 항목 필터링."""
import os, requests

KEY = os.environ["ECOS_KEY"]
BASE = "https://ecos.bok.or.kr/api"

# 통계목록 조회
url = f"{BASE}/StatisticTableList/{KEY}/json/kr/1/500"
r = requests.get(url, timeout=30)
data = r.json()
rows = data.get("StatisticTableList", {}).get("row", [])
print(f"엔트리 수: {len(rows)}")

keywords = ["외국인", "채권", "주식순매수", "증권투자"]
for row in rows:
    name = row.get("STAT_NAME", "") + row.get("ITEM_NAME", "")
    if any(k in name for k in keywords):
        print(f"  [{row.get('STAT_CODE')}] {row.get('STAT_NAME')} / {row.get('ITEM_NAME','')}")

# raw 응답 일부 확인
if not rows:
    print("응답 raw:", str(data)[:500])
