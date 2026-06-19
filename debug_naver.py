#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""네이버금융 외국인 순매수 접근 진단 스크립트"""
import requests
import datetime as dt

KST = dt.timezone(dt.timedelta(hours=9))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

def test_naver():
    # 어제 날짜
    today = dt.datetime.now(KST).date()
    yesterday = today - dt.timedelta(days=1)
    # 평일로 맞추기
    while yesterday.weekday() >= 5:
        yesterday -= dt.timedelta(days=1)
    date_str = yesterday.strftime("%Y%m%d")
    print(f"테스트 날짜: {date_str}")

    url = (f"https://finance.naver.com/sise/investorDealTrendDay.naver"
           f"?bizdate={date_str}&sosok=0")
    print(f"URL: {url}")

    # 1. 기본 요청
    print("\n[1] 기본 User-Agent 요청")
    try:
        r = requests.get(url, headers={"User-Agent": UA,
                                       "Referer": "https://finance.naver.com/"},
                         timeout=15, allow_redirects=True)
        print(f"  상태코드: {r.status_code}")
        print(f"  최종URL: {r.url}")
        print(f"  Content-Type: {r.headers.get('Content-Type', '')}")
        html = r.content.decode("euc-kr", errors="replace")
        print(f"  본문 앞 300자: {html[:300]}")
        if "외국인" in html:
            print("  → '외국인' 텍스트 발견 ✓")
        else:
            print("  → '외국인' 텍스트 없음 ✗")
    except Exception as ex:
        print(f"  예외: {ex}")

    # 2. 쿠키 없이 세션 요청
    print("\n[2] 세션 기반 요청 (메인 페이지 먼저)")
    try:
        s = requests.Session()
        s.headers.update({"User-Agent": UA})
        s.get("https://finance.naver.com/", timeout=10)
        r2 = s.get(url, headers={"Referer": "https://finance.naver.com/sise/"},
                   timeout=15)
        print(f"  상태코드: {r2.status_code}")
        html2 = r2.content.decode("euc-kr", errors="replace")
        if "외국인" in html2:
            print("  → '외국인' 텍스트 발견 ✓")
        else:
            print(f"  → '외국인' 없음. 본문: {html2[:200]}")
    except Exception as ex:
        print(f"  예외: {ex}")

    # 3. KOFIA DNS 확인
    print("\n[3] KOFIA 도메인 확인")
    import socket
    for host in ["freeboard.kofia.or.kr", "www.kofia.or.kr", "data.kofia.or.kr"]:
        try:
            ip = socket.gethostbyname(host)
            print(f"  {host} → {ip} ✓")
        except Exception as ex:
            print(f"  {host} → 실패: {ex}")

    # 4. www.kofia.or.kr 접근 시도
    print("\n[4] www.kofia.or.kr 접근")
    try:
        r3 = requests.get("https://www.kofia.or.kr", headers={"User-Agent": UA},
                          timeout=10)
        print(f"  상태코드: {r3.status_code}")
    except Exception as ex:
        print(f"  예외: {ex}")

if __name__ == "__main__":
    test_naver()
