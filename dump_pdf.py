#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FSS 일일 금융시장동향 PDF 전체 텍스트 덤프 — 외국인 순매수 항목 존재 여부 확인."""
import os, datetime as dt
from io import BytesIO
import requests, pdfplumber

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
KST = dt.timezone(dt.timedelta(hours=9))
API = "https://www.fss.or.kr/fss/kr/openApi/api/fnncMrkt.jsp"

today = dt.datetime.now(KST).date()
params = {"apiType": "json",
          "startDate": (today - dt.timedelta(days=7)).strftime("%Y%m%d"),
          "endDate": today.strftime("%Y%m%d"),
          "authKey": os.environ.get("FSS_AUTH_KEY", "").strip()}
r = requests.get(API, params=params, headers={"User-Agent": UA}, timeout=30)
root = r.json().get("reponse") or r.json().get("response") or r.json()
rows = root.get("result") or []
daily = sorted([x for x in rows if "일일 금융시장 동향" in (x.get("subject") or "")],
               key=lambda x: x.get("regDate", ""), reverse=True)
url = daily[0]["atchfileUrl"]
print("PDF:", url)
pdf = BytesIO(requests.get(url, timeout=60).content)
with pdfplumber.open(pdf) as p:
    text = "\n".join(pg.extract_text() or "" for pg in p.pages)

print("=" * 70)
for i, ln in enumerate(text.split("\n")):
    if any(k in ln for k in ["외국인", "외인", "순매수", "순매도", "채권"]):
        print(f"{i:3} | {ln}")
print("=" * 70)
print("총 라인수:", len(text.split("\n")))
