#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KOFIA freesis 데이터 API 엔드포인트/serviceId 탐침.
EC2(한국 IP)에서 실행. 페이지 HTML/JS에서 .do, serviceId, Stat 토큰 추출.
"""
import re, requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
H = {"User-Agent": UA, "Referer": "https://freesis.kofia.or.kr/"}

def get(url):
    r = requests.get(url, headers=H, timeout=30)
    print(f"\n### GET {url} -> {r.status_code} ({len(r.text)} bytes)")
    return r.text

# 1) 채권 메뉴 페이지
txt = get("https://freesis.kofia.or.kr/stat/FreeSIS.do?parentDivId=MSIS20000000000000")

# serviceId 후보 추출
ids = sorted(set(re.findall(r"STAT[A-Z]{3}\d{10}", txt)))
print("serviceId 후보:", ids[:60])

# .do / .json 엔드포인트 추출
endpoints = sorted(set(re.findall(r"[\w/]+\.(?:do|json)", txt)))
print("엔드포인트:", endpoints[:60])

# 외국인 관련 메뉴명 주변 텍스트
for m in re.finditer(r".{0,30}외국인.{0,40}", txt):
    print("  외국인:", m.group(0).replace("\n"," ").strip())

# 메인 JS 파일 경로
js = sorted(set(re.findall(r'src=["\']([^"\']+\.js)["\']', txt)))
print("JS 파일:", js[:30])
