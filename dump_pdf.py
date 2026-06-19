#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FSS 일일 금융시장동향 PDF 전체 텍스트 덤프 — 외국인 순매수 항목 존재 여부 확인.
PDF URL은 워크플로 로그에서 확인된 직접 링크 사용(인증키 불필요)."""
from io import BytesIO
import requests, pdfplumber

URL = ("https://www.fss.or.kr/fss/cmmn/file/fileDown.do?menuNo=200224"
       "&atchFileId=6a13ac164a0a41768ef3bf98d9bc2984&fileSn=1")
print("PDF:", URL)
pdf = BytesIO(requests.get(URL, timeout=60).content)
with pdfplumber.open(pdf) as p:
    text = "\n".join(pg.extract_text() or "" for pg in p.pages)

lines = text.split("\n")
print("=" * 72, "\n[전체 텍스트]\n", "=" * 72)
for i, ln in enumerate(lines):
    print(f"{i:3} | {ln}")
print("=" * 72)
print("총 라인수:", len(lines))
