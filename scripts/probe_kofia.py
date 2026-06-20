#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KOFIA freesis 데이터 API 탐침 2단계.
- 껍데기 페이지 원문 전체 출력
- 알려진 serviceId(STATBND0100000280=채권대차)로 데이터 API 후보 POST 시도
"""
import requests, json

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
H = {"User-Agent": UA, "Referer": "https://freesis.kofia.or.kr/"}

# 1) 껍데기 원문 전체
r = requests.get("https://freesis.kofia.or.kr/stat/FreeSIS.do?parentDivId=MSIS20000000000000",
                 headers=H, timeout=30)
print("===== 껍데기 페이지 원문 =====")
print(r.text)
print("===== /원문 =====\n")

# 2) 데이터 API 후보 엔드포인트 POST 시도 (채권대차 serviceId로)
candidates = [
    "https://freesis.kofia.or.kr/stat/FreeSISStat.do",
    "https://freesis.kofia.or.kr/stat/statTotalList.do",
    "https://freesis.kofia.or.kr/stat/getStatSearchList.do",
    "https://freesis.kofia.or.kr/websquare/engine/data/dataList.do",
]
payload = {"serviceId": "STATBND0100000280", "startDt": "20260601", "endDt": "20260618"}
for url in candidates:
    try:
        rr = requests.post(url, headers=H, json=payload, timeout=20)
        print(f"[POST json] {url} -> {rr.status_code} ({len(rr.text)}b) {rr.text[:200]!r}")
    except Exception as e:
        print(f"[POST json] {url} -> ERR {e}")
    try:
        rr = requests.post(url, headers=H, data=payload, timeout=20)
        print(f"[POST form] {url} -> {rr.status_code} ({len(rr.text)}b) {rr.text[:200]!r}")
    except Exception as e:
        print(f"[POST form] {url} -> ERR {e}")
