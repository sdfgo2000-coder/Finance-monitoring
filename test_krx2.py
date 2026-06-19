#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KRX getJsonData — 풀 브라우저 헤더 지문 시험. EC2에서 실행."""
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
B = "https://data.krx.co.kr"
J = B + "/comm/bldAttendant/getJsonData.cmd"
MENU = "MDC0201020301"
pay = {"bld": "dbms/MDC/STAT/standard/MDCSTAT02201", "locale": "ko_KR",
       "inqTpCd": "1", "trdVolVal": "2", "askBid": "3", "mktId": "ALL",
       "strtDd": "20260418", "endDd": "20260618",
       "share": "1", "money": "1", "csvxls_isNo": "false"}

FULL = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": B,
    "Referer": B + "/contents/MDC/MDI/mdiLoader/index.cmd?menuId=" + MENU,
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "X-Requested-With": "XMLHttpRequest",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

def show(name, r):
    print(f"  [{name}] {r.status_code} body={r.text[:180]!r}")

# V5: 풀헤더 + 메인+화면 워밍업
s = requests.Session(); s.headers["User-Agent"] = UA
s.get(B + "/contents/MDC/MAIN/main/index.cmd", timeout=20)
s.get(B + "/contents/MDC/MDI/mdiLoader/index.cmd?menuId=" + MENU, timeout=20)
print("warmup cookies:", sorted(s.cookies.keys()))
r = s.post(J, data=pay, headers=FULL, timeout=30); show("5-full-headers", r)

# V6: 풀헤더 + bldAttendant 사전 호출(getJsonData가 의존하는 onload)
s = requests.Session(); s.headers["User-Agent"] = UA
s.get(B + "/contents/MDC/MDI/mdiLoader/index.cmd?menuId=" + MENU, timeout=20)
# 화면 로딩 시 호출되는 부가 리소스
try:
    s.get(B + "/comm/bldAttendant/executeForResourceBundle.cmd?baseName=krx.mdc.i18n.component&key=B128.bld", timeout=20)
except Exception as e:
    print("  (resource bundle exc)", e)
r = s.post(J, data=pay, headers=FULL, timeout=30); show("6-full+resbundle", r)

# V7: gzip 인코딩 추가
s = requests.Session(); s.headers["User-Agent"] = UA
s.get(B + "/contents/MDC/MDI/mdiLoader/index.cmd?menuId=" + MENU, timeout=20)
h = dict(FULL); h["Accept-Encoding"] = "gzip, deflate, br"
r = s.post(J, data=pay, headers=h, timeout=30); show("7-full+gzip", r)

# V8: 동일 세션 2회(첫 호출이 세션 활성화)
s = requests.Session(); s.headers["User-Agent"] = UA
s.get(B + "/contents/MDC/MDI/mdiLoader/index.cmd?menuId=" + MENU, timeout=20)
r1 = s.post(J, data=pay, headers=FULL, timeout=30); show("8a-first", r1)
r2 = s.post(J, data=pay, headers=FULL, timeout=30); show("8b-second", r2)
