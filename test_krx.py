#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KRX getJsonData 접근 방식 진단 — EC2에서 실행. 어떤 변형이 데이터를 반환하는지 확인."""
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

def test(base):
    J = base + "/comm/bldAttendant/getJsonData.cmd"
    pay = {"bld": "dbms/MDC/STAT/standard/MDCSTAT02201", "locale": "ko_KR",
           "inqTpCd": "1", "trdVolVal": "2", "askBid": "3", "mktId": "ALL",
           "strtDd": "20260418", "endDd": "20260618",
           "share": "1", "money": "1", "csvxls_isNo": "false"}

    def show(name, r):
        body = r.text[:160].replace("\n", " ")
        ck = "; ".join(sorted(r.cookies.keys())) if r.cookies else "-"
        print(f"  [{name}] {r.status_code} cookies={ck} body={body!r}")

    print(f"=== BASE={base} ===")

    # 1) 워밍업 없음, 최소 헤더 (pykrx 스타일)
    s = requests.Session(); s.headers["User-Agent"] = UA
    try:
        r = s.post(J, data=pay, headers={"Referer": base + "/contents/MDC/MDI/mdiLoader/index.cmd"}, timeout=30)
        show("1-no-warmup-min", r)
    except Exception as e: print("  [1] EXC", e)

    # 2) 화면만 워밍업
    s = requests.Session(); s.headers["User-Agent"] = UA
    try:
        w = s.get(base + "/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201020301", timeout=20)
        print(f"  (warmup screen {w.status_code} setcookies={sorted(s.cookies.keys())})")
        r = s.post(J, data=pay, headers={"Referer": base + "/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201020301"}, timeout=30)
        show("2-screen-warmup", r)
    except Exception as e: print("  [2] EXC", e)

    # 3) 메인+화면 워밍업 + XHR 헤더
    s = requests.Session(); s.headers["User-Agent"] = UA
    try:
        s.get(base + "/contents/MDC/MAIN/main/index.cmd", timeout=20)
        s.get(base + "/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201020301", timeout=20)
        print(f"  (warmup main+screen setcookies={sorted(s.cookies.keys())})")
        r = s.post(J, data=pay, headers={
            "Referer": base + "/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201020301",
            "X-Requested-With": "XMLHttpRequest"}, timeout=30)
        show("3-full-warmup-xhr", r)
    except Exception as e: print("  [3] EXC", e)

    # 4) otp 워밍업(generate.cmd)
    s = requests.Session(); s.headers["User-Agent"] = UA
    try:
        s.get(base + "/", timeout=20)
        r = s.post(J, data=pay, headers={"Referer": base + "/"}, timeout=30)
        show("4-root-warmup", r)
    except Exception as e: print("  [4] EXC", e)

for base in ["https://data.krx.co.kr", "http://data.krx.co.kr"]:
    test(base)
