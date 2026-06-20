#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FSS 일일 금융시장동향 → 통합 조기경보지표 일일 모니터링 → 메일 발송
  지표(6): 주가(KOSPI) / 환율(원·달러) / 금리(국고3년) / ROK CDS / 신용스프레드 / 외인자금(2개월 누적)

트리거 기준
  주가  : 직전6개월 평균 대비  1단계 -10%,  2단계 -25%   (하락 위험)
  환율  : 직전6개월 평균 대비  1단계 +10%,  2단계 +25%   (상승 위험)
  금리  : 직전6개월 평균 대비  1단계 +60bp, 2단계 +120bp (상승 위험)
  ROK CDS / 신용스프레드 : 절대수준  1단계 100bp, 2단계 250bp
  외인자금(직전 2개월 누적 순매수) : 1단계 -5조, 2단계 -7조 (이하·순유출 위험)
종합결과 : 6개 중 2개 이상이 1단계↑ → 위기 1단계 / 2개 이상이 2단계 → 위기 2단계
"""
import os, re, ssl, sys, json, smtplib, calendar
import html as html_lib
import urllib.parse
import datetime as dt
from io import BytesIO
from xml.etree import ElementTree as ET
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr, parsedate_to_datetime, make_msgid
import requests, pdfplumber

# ── 설정 ────────────────────────────────────────────────────────────
SIX_MONTH_AVG = {"kospi": 5574, "fx": 1473, "ktb3": 3.27}

ECOS_SERIES = {
    "fx":    {"stat": "731Y001", "item": "0000001",   "cycle": "D"},
    "ktb3":  {"stat": "817Y002", "item": "010200000", "cycle": "D"},
    "kospi": {"stat": "802Y001", "item": "0001000",   "cycle": "D"},
}

ABS_TRIGGER  = (100, 250)
CRISIS_COUNT = 2

FOREIGN_TRIGGER = (-5.0, -7.0)

# 외인자금 일별 누적 이력: self-hosted 러너 홈에 영속 저장(체크아웃에 영향 없음).
# 매 실행 PDF '일중(당일)' 순매수(억원)를 적립 → 직전 2개월(base-2개월~base) 합산.
FOREIGN_HISTORY = (os.environ.get("FOREIGN_HISTORY")
                   or os.path.expanduser("~/.fss_monitor/foreign_history.csv"))
# 파서 버전: 채권 행 조건 강화 후 올려 이력 자동 재백필 트리거.
FOREIGN_PARSER_VER = 5
FOREIGN_VER_FILE   = FOREIGN_HISTORY.replace(".csv", ".ver")

LOOKBACK = 7
API = "https://www.fss.or.kr/fss/kr/openApi/api/fnncMrkt.jsp"
KST = dt.timezone(dt.timedelta(hours=9))

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

SAMSUNG_GROUPS = [
    ("삼성전자",                 ["삼성전자"],                              "samsung_electronics.png"),
    ("전자 계열 (SDI·전기·SDS)", ["삼성SDI", "삼성전기", "삼성SDS"],          "electronics_group.png"),
    ("바이오·물산",              ["삼성바이오로직스", "삼성물산"],            "bio_cnt.png"),
    ("금융 (생명·화재·증권·카드)", ["삼성생명", "삼성화재", "삼성증권", "삼성카드"], "finance.png"),
    ("기타 국내 계열사",          ["삼성중공업", "삼성E&A", "호텔신라", "제일기획", "에스원"], "others.png"),
]
ASSET_DIR          = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "news")
NEWS_PER_KEYWORD   = int(os.environ.get("NEWS_PER_KEYWORD", "6"))
NEWS_PER_GROUP     = int(os.environ.get("NEWS_PER_GROUP", "3"))
NEWS_CANDIDATES    = int(os.environ.get("NEWS_CANDIDATES", "8"))
NEWS_CUTOFF_HM     = (7, 11)
NEWS_SUMMARY_MODEL = os.environ.get("NEWS_SUMMARY_MODEL", "claude-opus-4-8")


# ── 1. 금감원 API ────────────────────────────────────────────────────
def list_daily_posts(auth_key, start, end):
    """[start, end] 구간의 '일일 금융시장 동향' 게시물을 regDate 내림차순으로 반환.
    각 원소: {"atchfileUrl", "regDate"}. (start, end: date)"""
    params = {"apiType": "json",
              "startDate": start.strftime("%Y%m%d"),
              "endDate": end.strftime("%Y%m%d"),
              "authKey": (auth_key or "").strip()}
    r = requests.get(API, params=params, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    data = r.json()
    root = data.get("reponse") or data.get("response") or data
    rows = root.get("result") or []
    daily = [x for x in rows if "일일 금융시장 동향" in (x.get("subject") or "")]
    daily.sort(key=lambda x: x.get("regDate", ""), reverse=True)
    if not daily:
        print(f"[진단] resultCode={root.get('resultCode')} resultMsg={root.get('resultMsg')} "
              f"resultCnt={root.get('resultCnt')}")
        print(f"[진단] 받은 제목들: {[x.get('subject') for x in rows]}")
    return daily


def fetch_daily_pdf_url(auth_key):
    today = dt.datetime.now(KST).date()
    daily = list_daily_posts(auth_key, today - dt.timedelta(days=LOOKBACK), today)
    if not daily:
        raise RuntimeError("일일 금융시장 동향 게시물을 찾지 못했습니다.")
    return daily[0]["atchfileUrl"], daily[0].get("regDate", "")


def download_pdf(url):
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return BytesIO(r.content)


# ── 2. PDF 추출 ──────────────────────────────────────────────────────
def _today_value(line):
    nums = []
    for t in line.split():
        if "↑" in t or "↓" in t:
            break
        if re.fullmatch(r"-?\d[\d,]*\.?\d*", t):
            nums.append(float(t.replace(",", "")))
    return nums[-1] if nums else None


def pdf_text(pdf_io):
    with pdfplumber.open(pdf_io) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def _parse_base_date(text):
    m = re.search(r"(\d{4})\.(\d{2})\.(\d{2})\([월화수목금토일]\)\s*기준", text)
    return (f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m
            else dt.datetime.now(KST).strftime("%Y-%m-%d"))


def extract(pdf_io, auth_key=None):
    text = pdf_text(pdf_io)
    v, in_cds = {}, False
    for ln in text.split("\n"):
        s = ln.strip()
        if "CDS Premium" in s:
            in_cds = True
        if s.startswith("KOSPI"):             v["kospi"] = _today_value(s)
        elif s.startswith("USDKRW"):          v["fx"]    = _today_value(s)
        elif "국고채(3년)" in s:              v["ktb3"]  = _today_value(s)
        elif "회사채(3년" in s:               v["corp3"] = _today_value(s)
        elif in_cds and s.startswith("한국"):  v["cds"]   = _today_value(s)

    miss = [k for k in ("kospi", "fx", "ktb3", "corp3", "cds") if v.get(k) is None]
    if miss:
        raise RuntimeError(f"추출 실패: {miss} (PDF 양식 변경 가능성)")
    assert 1000 < v["kospi"] < 20000 and 800 < v["fx"] < 2500
    assert 0 < v["ktb3"] < 15 and 0 < v["corp3"] < 20 and 0 < v["cds"] < 500

    v["base_date"] = _parse_base_date(text)
    v["spread"] = round((v["corp3"] - v["ktb3"]) * 100, 1)
    v["foreign_2m"] = compute_foreign_2m(text, v["base_date"], auth_key)
    return v


# ── 2-B. 외인 투자자금: PDF '일중(당일)' 순매수를 매일 누적 → 직전 2개월 합산 ──────
def _daily_col(line):
    """표 한 행에서 '일중 당일' 순매수를 억원 단위로 반환. 실패 시 None.
    행 구조: 라벨 [년중·년중·전월중·당월중](조원·소수) [전일·당일·잔액](억원·정수) [비중].
    억원 컬럼은 콤마 정수(소수점 없음) → [전일, 당일, 잔액]. 당일 = 끝에서 두 번째.
    """
    # pdfplumber가 천단위 숫자 '3,497,161'을 '3 ,497,161'처럼 쪼개는 경우 복구
    line = re.sub(r"(\d)\s+,", r"\1,", line)
    ints = []
    for t in line.split():
        if "." in t or "(" in t or "%" in t:
            continue
        c = t.replace(",", "")
        if re.fullmatch(r"[+-]?\d+", c):
            ints.append(int(c))
    if len(ints) >= 3:
        return ints[-2]          # 당일(억원), ints[-1]=잔액
    return None


def _prev_col(line):
    """표 한 행에서 '전일' 확정치(억원)를 반환. ints[-3]=전일, ints[-2]=당일, ints[-1]=잔액."""
    line = re.sub(r"(\d)\s+,", r"\1,", line)
    ints = []
    for t in line.split():
        if "." in t or "(" in t or "%" in t:
            continue
        c = t.replace(",", "")
        if re.fullmatch(r"[+-]?\d+", c):
            ints.append(int(c))
    if len(ints) >= 4:
        return ints[-3]   # 전일(억원) 확정치
    return None


def _pdf_daily_today(text):
    """PDF '외국인 유가증권 투자' 표 → (주식 합계 당일, 채권 순매수 당일) 억원. 실패 None.
    채권 행은 '순매수(만기상환'으로 시작하는 고유 패턴으로 한정."""
    stock = bond = None
    in_sec = False
    for ln in text.split("\n"):
        s = ln.strip()
        if "외국인" in s and "유가증권 투자" in s:
            in_sec = True
            continue
        if not in_sec:
            continue
        if stock is None and s.startswith("합계"):
            stock = _daily_col(s)
        elif bond is None and "만기상환" in s and s.startswith("순매수"):
            bond = _daily_col(s)
        if stock is not None and bond is not None:
            break
    return stock, bond


def _pdf_daily_prev(text):
    """PDF → (주식 합계 전일 확정치, 채권 순매수 전일 확정치) 억원. 실패 None."""
    stock = bond = None
    in_sec = False
    for ln in text.split("\n"):
        s = ln.strip()
        if "외국인" in s and "유가증권 투자" in s:
            in_sec = True
            continue
        if not in_sec:
            continue
        if stock is None and s.startswith("합계"):
            stock = _prev_col(s)
        elif bond is None and "만기상환" in s and s.startswith("순매수"):
            bond = _prev_col(s)
        if stock is not None and bond is not None:
            break
    return stock, bond


def _months_back(d, n):
    """날짜 d에서 n개월 전 같은 날(말일 초과 시 해당 월 말일로 보정)."""
    m = d.month - 1 - n
    y = d.year + m // 12
    m = m % 12 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return dt.date(y, m, day)


def _load_history():
    out = {}
    try:
        with open(FOREIGN_HISTORY, encoding="utf-8") as f:
            for line in f:
                p = line.strip().split(",")
                if len(p) == 3:
                    out[p[0]] = (float(p[1]), float(p[2]))
    except FileNotFoundError:
        pass
    return out


def _save_history(hist):
    os.makedirs(os.path.dirname(FOREIGN_HISTORY), exist_ok=True)
    with open(FOREIGN_HISTORY, "w", encoding="utf-8") as f:
        for d in sorted(hist):
            s, b = hist[d]
            f.write(f"{d},{s},{b}\n")


def _date_chunks(start, end, days=28):
    """[start, end]를 days 이하 길이의 부분구간으로 분할(FSS 개인키 조회한도 1개월 회피)."""
    cur = start
    while cur <= end:
        nxt = min(cur + dt.timedelta(days=days), end)
        yield cur, nxt
        cur = nxt + dt.timedelta(days=1)


def _backfill_history(auth_key, base, cutoff, hist):
    """[cutoff, base] 구간 PDF를 받아 각 날짜의 '당일' 순매수를 이력에 채움.
    FSS 개인 인증키는 1개월 조회한도가 있어 구간을 4주 단위로 쪼개 목록 조회.
    파싱 성공 시 항상 덮어써 과거 오적립도 자가치유."""
    if not auth_key:
        print("[외인자금] FSS 인증키 없음 → 과거 PDF 백필 생략")
        return hist
    posts, seen = [], set()
    for cs, ce in _date_chunks(cutoff, base, 28):
        try:
            for p in list_daily_posts(auth_key, cs, ce):
                u = p.get("atchfileUrl")
                if u and u not in seen:
                    seen.add(u)
                    posts.append(p)
        except Exception as ex:
            print(f"[외인자금] 백필 목록조회 실패({cs}~{ce}): {ex}")
    # 날짜 오름차순 처리: 당일 잠정치 먼저 → 다음날 PDF의 전일 확정치가 나중에 덮어씀
    posts.sort(key=lambda p: p.get("regDate", ""))
    added = 0
    for p in posts:
        url = p.get("atchfileUrl")
        if not url:
            continue
        try:
            text = pdf_text(download_pdf(url))
        except Exception as ex:
            print(f"[외인자금] 백필 PDF 실패({p.get('regDate')}): {ex}")
            continue
        d = _parse_base_date(text)
        if not (cutoff.isoformat() <= d <= base.isoformat()):
            continue
        # 전일 확정치를 전날 날짜로 저장 (잠정→확정 자동교정)
        base_d = dt.date.fromisoformat(d)
        prev_d = (base_d - dt.timedelta(days=1)).isoformat()
        st_prev, bo_prev = _pdf_daily_prev(text)
        if st_prev is not None and bo_prev is not None and cutoff.isoformat() <= prev_d:
            hist[prev_d] = (st_prev, bo_prev)
        # 당일 잠정치 (다음날 PDF에서 확정치로 덮어씌워짐)
        st, bo = _pdf_daily_today(text)
        if st is not None and bo is not None:
            if d not in hist:
                added += 1
            hist[d] = (st, bo)
    if posts:
        _save_history(hist)
        print(f"[외인자금] 과거 PDF 백필: 신규 {added}건 / 조회 {len(posts)}건")
    return hist


def compute_foreign_2m(text, base_date_str, auth_key=None):
    """직전 2개월(base-2개월 ~ base) 외국인 순매수 누적(조원).
      주력: PDF '일중(당일)' 순매수(억원)를 이력에 적립 → 윈도우 합산(정확).
      이력이 윈도우를 못 덮으면 과거 PDF를 일괄 백필하여 즉시 완성.
      그래도 부족하면 PDF '전월+당월 월중' 근사로 폴백.
    """
    try:
        base = dt.date.fromisoformat(base_date_str)
    except ValueError:
        base = dt.datetime.now(KST).date()
    cutoff = _months_back(base, 2)

    stock_today, bond_today = _pdf_daily_today(text)
    stock_prev, bond_prev = _pdf_daily_prev(text)
    hist = _load_history()
    prev_date = (base - dt.timedelta(days=1))
    # 전일 확정치로 덮어씀 (당일 잠정치 → 확정치 자동 교정)
    if stock_prev is not None and bond_prev is not None:
        prev_str = prev_date.isoformat()
        hist[prev_str] = (stock_prev, bond_prev)
        print(f"[외인자금] 전일({prev_str}) 확정치 갱신: "
              f"주식 {stock_prev:+,}억 · 채권 {bond_prev:+,}억")
    if stock_today is not None and bond_today is not None:
        hist[base_date_str] = (stock_today, bond_today)
        _save_history(hist)
        print(f"[외인자금] 당일({base_date_str}) 순매수 적립(잠정): "
              f"주식 {stock_today:+,}억 · 채권 {bond_today:+,}억")
    else:
        if stock_prev is not None:
            _save_history(hist)
        print("[외인자금] PDF 일중(당일) 파싱 실패 → 당일 적립 생략")

    # 파서 버전이 올라가면 이력을 전부 재백필하여 오적립 자가치유
    try:
        saved_ver = int(open(FOREIGN_VER_FILE).read().strip())
    except Exception:
        saved_ver = 0
    force_backfill = saved_ver < FOREIGN_PARSER_VER

    # cutoff가 주말·공휴일이면 첫 영업일 게시물이 며칠 뒤일 수 있어 여유(5일) 허용
    cover_need = cutoff + dt.timedelta(days=5)

    def _window(h):
        ds = sorted(dt.date.fromisoformat(d) for d in h)
        win = [h[d.isoformat()] for d in ds if cutoff <= d <= base]
        earliest = next((d for d in ds if cutoff <= d <= base), None)
        return win, earliest

    window, earliest = _window(hist)
    if force_backfill or not (earliest is not None and earliest <= cover_need):
        if force_backfill:
            print(f"[외인자금] 파서 버전 {saved_ver}→{FOREIGN_PARSER_VER} 업 → 전체 재백필")
        hist = _backfill_history(auth_key, base, cutoff, hist)
        window, earliest = _window(hist)
        # 버전 파일 갱신
        try:
            os.makedirs(os.path.dirname(FOREIGN_VER_FILE), exist_ok=True)
            open(FOREIGN_VER_FILE, "w").write(str(FOREIGN_PARSER_VER))
        except Exception:
            pass

    if earliest is not None and earliest <= cover_need and window:
        eok = sum(s + b for s, b in window)
        result = round(eok / 10000, 2)
        print(f"[외인자금] 직전2개월({cutoff}~{base}) 일별누적 = {result:+.2f}조 "
              f"(영업일 {len(window)}건)")
        return result

    print(f"[외인자금] 누적 이력 부족(보유 시작 {earliest}, 필요 {cutoff}) "
          f"→ PDF 전월+당월 근사로 폴백")
    return _pdf_foreign_2m(text)


# ── 2-C. (폴백) 외인 투자자금: PDF '전월+당월 월중'에서 직접 파싱 ────────────────
def _two_month_cols(line):
    """표 한 행에서 '월중' 두 컬럼(전월, 당월)을 (전월, 당월) 튜플로 반환(조원). 실패 시 None.
    행 구조: 라벨 [년중, 년중, 월중, 월중](조원·소수) [일중, 일중, 잔액](억원·정수) [비중].
    조원 컬럼만 소수점을 가지므로(콤마 없는 소수) 그것만 모아 마지막 2개(=전월·당월 월중)를 취함.
    """
    decimals = [float(t) for t in line.split() if re.fullmatch(r"[+-]?\d+\.\d+", t)]
    if len(decimals) >= 2:
        return decimals[-2], decimals[-1]   # (전월 월중, 당월 월중)
    return None


def _pdf_foreign_2m(text):
    """FSS PDF '외국인 유가증권 투자' 표 → 직전 2개월(전월+당월) 누적 순매수(조원).
      주식: '합계' 행(코스피+코스닥) 월중 2개 합산
      채권: '순매수' 행(만기상환 미감안) 월중 2개 합산
    월중 컬럼 단위는 조원(표 머리글 명시). 실패 시 None.
    """
    stock = bond = None
    in_sec = False
    for ln in text.split("\n"):
        s = ln.strip()
        if "외국인" in s and "유가증권 투자" in s:
            in_sec = True
            continue
        if not in_sec:
            continue
        if stock is None and s.startswith("합계"):
            stock = _two_month_cols(s)
        elif bond is None and "만기상환" in s and s.startswith("순매수"):   # 채권 순매수(만기상환 등은 미감안)
            bond = _two_month_cols(s)
        if stock is not None and bond is not None:
            break

    if stock is None and bond is None:
        print("[외인자금] PDF 표 파싱 실패 → 지표 N/A")
        return None

    total, parts = 0.0, []
    if stock is not None:
        ssum = round(stock[0] + stock[1], 2)
        total += ssum
        parts.append(f"주식(코스피+코스닥) 전월 {stock[0]:+.1f} + 당월 {stock[1]:+.1f} = {ssum:+.1f}")
    if bond is not None:
        bsum = round(bond[0] + bond[1], 2)
        total += bsum
        parts.append(f"채권 전월 {bond[0]:+.1f} + 당월 {bond[1]:+.1f} = {bsum:+.1f}")
    result = round(total, 2)
    for p in parts:
        print("[외인자금]   " + p)
    print(f"[외인자금] 직전2개월 누적 합산 = {result:+.2f}조")
    return result


# ── 3. 분석 ──────────────────────────────────────────────────────────
def _stage_down(x, t1, t2):
    return 2 if x <= t2 else (1 if x <= t1 else 0)


def _stage_up(x, t1, t2):
    return 2 if x >= t2 else (1 if x >= t1 else 0)


def ecos_six_month_avg():
    key = (os.environ.get("ECOS_KEY") or "").strip()
    if not key:
        print("[ECOS] 키 없음 → 6개월 평균은 설정값 사용")
        return {}
    today = dt.datetime.now(KST).date()
    first_this = today.replace(day=1)
    end = first_this - dt.timedelta(days=1)
    m6 = first_this.year * 12 + (first_this.month - 1) - 6
    start = dt.date(m6 // 12, m6 % 12 + 1, 1)
    s, e = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    print(f"[ECOS] 직전6개월 구간: {s} ~ {e}")
    out = {}
    for name, c in ECOS_SERIES.items():
        try:
            url = (f"https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/1000/"
                   f"{c['stat']}/{c['cycle']}/{s}/{e}/{c['item']}")
            r = requests.get(url, timeout=30); r.raise_for_status()
            j = r.json()
            rows = (j.get("StatisticSearch") or {}).get("row") or []
            vals = [float(x["DATA_VALUE"]) for x in rows
                    if x.get("DATA_VALUE") not in (None, "", "-")]
            if vals:
                out[name] = round(sum(vals) / len(vals), 4)
                print(f"[ECOS] {name}: {len(vals)}건, 6개월평균={out[name]}")
            else:
                rs = j.get("RESULT") or {}
                print(f"[ECOS] {name} 데이터없음 → 설정값. 응답={rs or list(j)[:3]}")
        except Exception as ex:
            print(f"[ECOS] {name} 실패 → 설정값: {ex}")
    return out


def analyze(d, avg=None, foreign_2m=None):
    a = {**SIX_MONTH_AVG, **(avg or {})}
    rows = []

    t1, t2 = a["kospi"] * 0.90, a["kospi"] * 0.75
    rows.append({"name": "주가 (KOSPI)", "short": "주가", "unit": "pt",
                 "t1": f"{t1:,.0f}", "t2": f"{t2:,.0f}", "val": f"{d['kospi']:,.1f}",
                 "stage": _stage_down(d["kospi"], t1, t2), "avg": f"{a['kospi']:,}",
                 "sub": ("△10%", "△25%", f"{d['kospi']/a['kospi']-1:+.0%}")})

    t1, t2 = a["fx"] * 1.10, a["fx"] * 1.25
    rows.append({"name": "환율 (원/달러)", "short": "환율", "unit": "원",
                 "t1": f"{t1:,.0f}", "t2": f"{t2:,.0f}", "val": f"{d['fx']:,.1f}",
                 "stage": _stage_up(d["fx"], t1, t2), "avg": f"{a['fx']:,}",
                 "sub": ("+10%", "+25%", f"{d['fx']/a['fx']-1:+.0%}")})

    t1, t2 = a["ktb3"] + 0.60, a["ktb3"] + 1.20
    rows.append({"name": "금리 (국고3년)", "short": "금리", "unit": "%",
                 "t1": f"{t1:.2f}", "t2": f"{t2:.2f}", "val": f"{d['ktb3']:.2f}",
                 "stage": _stage_up(d["ktb3"], t1, t2), "avg": f"{a['ktb3']}",
                 "sub": ("+60bp", "+120bp", f"{(d['ktb3']-a['ktb3'])*100:+.0f}bp")})

    a1, a2 = ABS_TRIGGER
    rows.append({"name": "ROK CDS", "short": "ROK CDS", "unit": "bp",
                 "t1": f"{a1}", "t2": f"{a2}", "val": f"{d['cds']:.0f}",
                 "stage": _stage_up(d["cds"], a1, a2), "sub": None})
    rows.append({"name": "신용스프레드 (회사채3년AA- − 국고3년)", "short": "신용스프레드", "unit": "bp",
                 "t1": f"{a1}", "t2": f"{a2}", "val": f"{d['spread']:.0f}",
                 "stage": _stage_up(d["spread"], a1, a2), "sub": None})

    f1, f2 = FOREIGN_TRIGGER
    if foreign_2m is None:
        rows.append({"name": "외인 순매수 (직전 2개월 누적·코스피·코스닥·채권)", "short": "외인자금",
                     "unit": "조원", "t1": f"{f1:.0f}", "t2": f"{f2:.0f}",
                     "val": "N/A", "stage": 0, "sub": None})
    else:
        rows.append({"name": "외인 순매수 (직전 2개월 누적·코스피·코스닥·채권)", "short": "외인자금",
                     "unit": "조원", "t1": f"{f1:.0f}", "t2": f"{f2:.0f}",
                     "val": f"{foreign_2m:+.2f}",
                     "stage": _stage_down(foreign_2m, f1, f2), "sub": None})

    n1 = sum(1 for r in rows if r["stage"] >= 1)
    n2 = sum(1 for r in rows if r["stage"] == 2)
    result = "위기 2단계" if n2 >= CRISIS_COUNT else ("위기 1단계" if n1 >= CRISIS_COUNT else "정상")

    normal = sum(1 for r in rows if r["stage"] == 0)
    breaches = [f"{r['short']} {r['stage']}단계" for r in rows if r["stage"] >= 1]
    summary = f"{normal}개 지표 정상" + (", " + ", ".join(breaches) if breaches else "")
    return {"rows": rows, "result": result, "summary": summary, "date": d["base_date"]}


# ── 3-B. 삼성 계열사 신문기사 수집 ──────────────────────────────────
def _strip_html(s):
    return html_lib.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def news_window():
    h, m = NEWS_CUTOFF_HM
    now = dt.datetime.now(KST)
    end = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if end > now:
        end -= dt.timedelta(days=1)
    start = end - dt.timedelta(days=1)
    while start.weekday() >= 5:
        start -= dt.timedelta(days=1)
    return start, end


def _in_window(items, start, end):
    fresh = [x for x in items if x.get("date") and start <= x["date"] <= end]
    return fresh or items


def _tokens(title):
    return set(re.findall(r"[가-힣a-zA-Z0-9]{2,}", (title or "").lower()))


def _cluster_coverage(articles):
    clusters = []
    for a in articles:
        t = _tokens(a["title"])
        hit = None
        for c in clusters:
            inter = len(t & c["toks"])
            union = len(t | c["toks"]) or 1
            if inter / union >= 0.5 or (min(len(t), len(c["toks"])) and
                                        inter / min(len(t), len(c["toks"])) >= 0.7):
                hit = c
                break
        if hit:
            hit["n"] += 1
            hit["toks"] |= t
            if not hit["rep"].get("desc") and a.get("desc"):
                a["keyword"] = hit["rep"].get("keyword", a.get("keyword"))
                hit["rep"] = a
        else:
            clusters.append({"rep": a, "toks": t, "n": 1})
    out = []
    for c in clusters:
        c["rep"]["coverage"] = c["n"]
        out.append(c["rep"])
    return out


def _naver_news(keyword, cid, secret, n):
    r = requests.get(
        "https://openapi.naver.com/v1/search/news.json",
        params={"query": keyword, "display": max(n * 3, 10), "sort": "date"},
        headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret},
        timeout=20)
    r.raise_for_status()
    out = []
    for it in r.json().get("items", []):
        try:
            d = parsedate_to_datetime(it.get("pubDate")).astimezone(KST)
        except Exception:
            d = None
        out.append({"title": _strip_html(it.get("title")),
                    "link": it.get("originallink") or it.get("link"),
                    "source": "", "desc": _strip_html(it.get("description")), "date": d})
    return out


def _google_news(keyword, n, days=2):
    q = urllib.parse.quote(f"{keyword} when:{days}d")
    url = f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
    r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for item in root.findall(".//item")[:max(n * 3, 10)]:
        title = (item.findtext("title") or "").strip()
        src = (item.findtext("source") or "").strip()
        if src and title.endswith(f" - {src}"):
            title = title[: -(len(src) + 3)]
        try:
            d = parsedate_to_datetime(item.findtext("pubDate")).astimezone(KST)
        except Exception:
            d = None
        out.append({"title": title, "link": item.findtext("link"),
                    "source": src, "date": d})
    return out


def _fetch_keyword(keyword, naver, n, start, end):
    days = max(2, int((dt.datetime.now(KST) - start).total_seconds() // 86400) + 1)
    if naver:
        try:
            items = _naver_news(keyword, naver[0], naver[1], n)
            if items:
                return _in_window(items, start, end)[:n]
        except Exception as ex:
            print(f"[NEWS] 네이버 실패({keyword}) → 구글뉴스 폴백: {ex}")
    try:
        return _in_window(_google_news(keyword, n, days), start, end)[:n]
    except Exception as ex:
        print(f"[NEWS] 구글뉴스 실패({keyword}): {ex}")
        return []


def collect_news():
    cid = (os.environ.get("NAVER_CLIENT_ID") or "").strip()
    secret = (os.environ.get("NAVER_CLIENT_SECRET") or "").strip()
    naver = (cid, secret) if cid and secret else None
    start, end = news_window()
    print(f"[NEWS] 소스: {'네이버(우선)+구글RSS' if naver else '구글뉴스 RSS'}"
          f" | 구간: {start:%m/%d %H:%M} ~ {end:%m/%d %H:%M} KST")
    groups = []
    for gname, keywords, image in SAMSUNG_GROUPS:
        seen, articles = set(), []
        for kw in keywords:
            for a in _fetch_keyword(kw, naver, NEWS_PER_KEYWORD, start, end):
                title = a.get("title")
                if not title or not a.get("link"):
                    continue
                key = re.sub(r"\s+", "", title)[:40]
                if key in seen:
                    continue
                seen.add(key)
                a["keyword"] = kw
                articles.append(a)
        articles = _cluster_coverage(articles)
        articles.sort(key=lambda x: (x.get("coverage", 1),
                                     x.get("date") or dt.datetime.min.replace(tzinfo=KST)),
                      reverse=True)
        groups.append({"name": gname, "image": image,
                       "articles": articles[:NEWS_CANDIDATES]})
        print(f"[NEWS] {gname}: 후보 {len(articles[:NEWS_CANDIDATES])}건"
              f" (보도량 최대 {max([a.get('coverage',1) for a in articles], default=0)})")
    return groups


# ── 3-C. 기사 선별 + 한 줄 요약 ─────────────────────────────────────
def _trim_groups(groups):
    for g in groups:
        g["articles"] = g["articles"][:NEWS_PER_GROUP]


def curate_and_summarize(groups):
    if not any(g["articles"] for g in groups):
        return
    if not (os.environ.get("ANTHROPIC_API_KEY") or "").strip():
        print("[AI] ANTHROPIC_API_KEY 없음 → 보도량순 선별·요약 생략")
        return _trim_groups(groups)
    try:
        import anthropic
    except ImportError:
        print("[AI] anthropic 미설치 → 보도량순 선별·요약 생략")
        return _trim_groups(groups)
    payload = [{"g": gi, "group": g["name"],
                "candidates": [{"i": i, "title": a["title"],
                                "coverage": a.get("coverage", 1),
                                "source": a.get("source", ""),
                                "desc": (a.get("desc") or "")[:200]}
                               for i, a in enumerate(g["articles"])]}
               for gi, g in enumerate(groups) if g["articles"]]
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["groups"],
        "properties": {
            "groups": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["g", "picks"],
                    "properties": {
                        "g": {"type": "integer"},
                        "picks": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["i", "summary", "press"],
                                "properties": {
                                    "i": {"type": "integer"},
                                    "summary": {"type": "string"},
                                    "press": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
        },
    }
    system = (f"너는 삼성그룹 계열사 신문스크랩을 만드는 한국어 편집기자다. "
              f"각 그룹의 후보 기사 중 독자가 가장 많이 볼 만한(화제성 높은) 기사를 "
              f"중요한 순서대로 최대 {NEWS_PER_GROUP}건 고른다. 판단 기준: "
              f"① coverage(같은 사안을 보도한 언론사 수 — 클수록 화제성 높음) "
              f"② 사업·실적·주가·인사·규제 등 회사에 미치는 영향의 크기 "
              f"③ 단순 시황·광고성·중복성 기사는 제외. "
              f"선택한 기사마다 40자 내외 평서문 한 문장 요약(summary)을 쓴다 — "
              f"과장·추측 금지, 제목 단순반복 금지. press 는 출처를 보고 한국 언론사 "
              f"약칭(예: 한경, 매경, 서경, 조선, 중앙, 동아, 연합, 머니투데이→머투, "
              f"이데일리, 전자신문→전자, 파이낸셜뉴스→F/N)을 1~3자로, 모르면 빈 문자열. "
              f"모든 입력 그룹(g)에 대해 결과를 반드시 반환한다.")
    try:
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=NEWS_SUMMARY_MODEL, max_tokens=4000, system=system,
            messages=[{"role": "user",
                       "content": json.dumps(payload, ensure_ascii=False)}],
            output_config={"format": {"type": "json_schema", "schema": schema}})
        text = next((b.text for b in resp.content if b.type == "text"), "")
        result = {r["g"]: r["picks"] for r in json.loads(text).get("groups", [])}
        for gi, g in enumerate(groups):
            picks = result.get(gi)
            if not picks:
                g["articles"] = g["articles"][:NEWS_PER_GROUP]
                continue
            chosen = []
            for p in picks[:NEWS_PER_GROUP]:
                i = p.get("i")
                if isinstance(i, int) and 0 <= i < len(g["articles"]):
                    a = g["articles"][i]
                    a["summary"] = (p.get("summary") or "").strip()
                    a["press"] = (p.get("press") or "").strip()
                    chosen.append(a)
            g["articles"] = chosen or g["articles"][:NEWS_PER_GROUP]
        print(f"[AI] {NEWS_SUMMARY_MODEL} 선별+요약 완료: "
              + ", ".join(f"{g['name']} {len(g['articles'])}건" for g in groups))
    except Exception as ex:
        print(f"[AI] 선별·요약 실패 → 보도량순 상위 표시: {ex}")
        _trim_groups(groups)


def _news_card(g, cid, has_img):
    esc = html_lib.escape
    banner = (f'<img src="cid:{cid}" width="100%" alt="" '
              f'style="display:block;width:100%;height:auto;border:0">' if has_img else "")
    arts = ""
    for a in g["articles"]:
        press = a.get("press") or a.get("source") or ""
        tag = (f' <span style="color:#8a93a0;font-weight:400;font-size:12px">'
               f'({esc(press)})</span>' if press else "")
        title = (f'<a href="{esc(a["link"], quote=True)}" '
                 f'style="color:#1a2b45;text-decoration:none;font-weight:700;'
                 f'font-size:13.5px;line-height:1.35">{esc(a["title"])}{tag}</a>')
        summ = a.get("summary")
        sub = (f'<div style="color:#5b6573;font-size:12px;line-height:1.4;'
               f'margin-top:2px">· {esc(summ)}</div>' if summ else "")
        arts += f'<div style="margin-bottom:9px">{title}{sub}</div>'
    return (f'<div style="border:1px solid #e3e6ea;border-radius:8px;overflow:hidden;'
            f'background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.04)">{banner}'
            f'<div style="padding:11px 13px 6px">'
            f'<div style="display:inline-block;font-weight:800;font-size:12.5px;color:#1a3c6e;'
            f'background:#eef2f8;border-radius:4px;padding:2px 8px;margin-bottom:9px">'
            f'[{esc(g["name"])}]</div>{arts}</div></div>')


def build_news_section(groups, date_label=""):
    used = [g for g in (groups or []) if g.get("articles")]
    if not used:
        return "", []
    images, cards = [], []
    for idx, g in enumerate(used):
        cid = f"newsimg{idx}"
        path = os.path.join(ASSET_DIR, g.get("image", ""))
        has_img = bool(g.get("image")) and os.path.exists(path)
        if has_img:
            images.append((cid, path))
        cards.append(_news_card(g, cid, has_img))

    rows = ""
    for r in range(0, len(cards), 2):
        left = cards[r]
        right = cards[r + 1] if r + 1 < len(cards) else ""
        rows += (f'<tr>'
                 f'<td width="50%" valign="top" style="padding:6px">{left}</td>'
                 f'<td width="50%" valign="top" style="padding:6px">{right}</td></tr>')
    table = f'<table width="100%" style="border-collapse:collapse;table-layout:fixed">{rows}</table>'

    title_bar = (f'<div style="display:flex;align-items:baseline;justify-content:space-between;'
                 f'border-bottom:2px solid #1a3c6e;padding:0 6px 8px;margin-bottom:4px">'
                 f'<span style="font-size:19px;font-weight:800;color:#152a4e">📰 삼성그룹 신문스크랩</span>'
                 f'<span style="font-size:12px;color:#8a93a0">{html_lib.escape(date_label)}</span></div>')
    foot = ('<div style="font-size:11px;color:#aab;line-height:1.6;padding:8px 6px 0">'
            '※ 전일 07:11~금일 07:11(월요일은 금요일 07:11부터) 수집 · 보도량(다룬 언론사 수)과 '
            '중요도 기준으로 AI가 카테고리별 3건 선별 · 한 줄 요약은 AI 자동생성으로 부정확할 수 있음.</div>')
    section = (f'<div style="padding:14px 16px 6px;background:#f4f5f7">'
               f'{title_bar}{table}{foot}</div>')
    return section, images


# ── 4. 메일 본문 ────────────────────────────────────────────────────
def build_email(an, news_html=""):
    res = an["result"]
    rc = {"정상": "#1e7e34", "위기 1단계": "#e67e22", "위기 2단계": "#c0392b"}[res]
    rows = an["rows"]
    total = sum(2 if r.get("sub") else 1 for r in rows)

    body, first = "", True
    for r in rows:
        red = r["stage"] >= 1
        vcol = "#c0392b" if red else "#222"
        td = 'padding:8px 11px;border:1px solid #dcdcdc'
        cells = (f'<td style="{td}">{r["name"]}</td>'
                 f'<td style="{td};text-align:center;color:#666">{r["unit"]}</td>'
                 f'<td style="{td};text-align:right">{r["t1"]}</td>'
                 f'<td style="{td};text-align:right">{r["t2"]}</td>'
                 f'<td style="{td};text-align:right;font-weight:700;color:{vcol}">{r["val"]}</td>')
        if first:
            cells += (f'<td rowspan="{total}" style="{td};text-align:center;vertical-align:middle;'
                      f'font-weight:800;font-size:18px;color:{rc};background:#fafbfc;width:96px">{res}</td>')
            first = False
        body += f'<tr>{cells}</tr>'
        if r.get("sub"):
            s1, s2, sv = r["sub"]
            sc = "#c0392b" if red else "#999"
            st = 'padding:5px 11px;border:1px solid #dcdcdc;font-size:12px'
            body += (f'<tr style="background:#f6f9fc">'
                     f'<td style="{st};color:#777">· 직전6개월 평균({r["avg"]}) 比</td>'
                     f'<td style="{st}"></td>'
                     f'<td style="{st};text-align:right;color:#999">{s1}</td>'
                     f'<td style="{st};text-align:right;color:#999">{s2}</td>'
                     f'<td style="{st};text-align:right;color:{sc}">{sv}</td></tr>')

    return f"""<!doctype html><html><body style="margin:0;background:#f4f5f7;padding:22px;
font-family:-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#222">
<div style="max-width:660px;margin:0 auto;background:#fff;border-radius:10px;overflow:hidden;
box-shadow:0 1px 5px rgba(0,0,0,.08)">
  <div style="background:#1a3c6e;color:#fff;padding:18px 22px">
    <div style="font-size:13px;opacity:.85">금융감독원 일일 금융시장 동향 기반</div>
    <div style="font-size:20px;font-weight:800;margin-top:2px">통합 조기경보지표 일일 모니터링</div>
    <div style="font-size:13px;opacity:.9;margin-top:6px">{an['date']} 기준</div>
  </div>
  <div style="padding:14px 22px 4px">
    <div style="padding:10px 14px;border-radius:6px;background:#f1f4f8;margin-bottom:12px">
      <span style="font-weight:700">통합 조기경보지표 :</span>
      <span style="color:{rc};font-weight:700"> {an['summary']}</span>
      <span style="float:right;font-weight:800;color:{rc}">모니터링 결과: {res}</span>
    </div>
    <table style="width:100%;border-collapse:collapse;font-size:14px">
      <thead><tr style="background:#eef2f7;color:#444;font-size:12px">
        <th style="padding:8px 11px;border:1px solid #dcdcdc;text-align:left">지표</th>
        <th style="padding:8px 11px;border:1px solid #dcdcdc">단위</th>
        <th style="padding:8px 11px;border:1px solid #dcdcdc">트리거 1단계</th>
        <th style="padding:8px 11px;border:1px solid #dcdcdc">트리거 2단계</th>
        <th style="padding:8px 11px;border:1px solid #dcdcdc">지표값 ({an['date'][5:]})</th>
        <th style="padding:8px 11px;border:1px solid #dcdcdc">모니터링 결과</th>
      </tr></thead>
      <tbody>{body}</tbody>
    </table>
    <div style="margin:14px 0 4px;font-size:11px;color:#9aa;line-height:1.6">
      트리거 — 주가: 6개월평균 대비 1단계 −10%/2단계 −25% · 환율: +10%/+25% ·
      금리: +60bp/+120bp · CDS·스프레드: 절대 100bp/250bp · 외인자금: 직전2개월누적 −5조/−7조<br>
      종합결과 — 2개 이상 지표가 1단계↑ 진입 시 위기 1단계, 2개 이상 2단계 진입 시 위기 2단계 ·
      기준 초과는 <span style="color:#c0392b">빨간색</span> 표시<br>
      ※ 직전6개월 평균은 ECOS 자동계산(미연동 지표는 설정값) · 외인자금은 직전 2개월(당일~2개월전)
      일별 순매수 누적(주식: 코스피+코스닥 합계, 채권: 순매수 / 구간 PDF 일중 순매수 합산, 누락 시 전월+당월 근사) ·
      출처: 금융감독원 일일 금융시장 동향. 정확성 보장하지 않음.
    </div>
  </div>
  {news_html}
</div></body></html>"""


# ── 5. 발송 ─────────────────────────────────────────────────────────
def _attach_inline_images(root, html, images):
    for cid, path in images or []:
        real = make_msgid(domain="fss.local")
        html = html.replace(f"cid:{cid}", f"cid:{real[1:-1]}")
        try:
            with open(path, "rb") as f:
                img = MIMEImage(f.read())
        except Exception as ex:
            print(f"[NEWS] 이미지 첨부 실패({path}): {ex}")
            continue
        img.add_header("Content-ID", real)
        img.add_header("Content-Disposition", "inline", filename=os.path.basename(path))
        root.attach(img)
    return html


def send_email(subject, html, images=None):
    host, user, pwd = (os.environ.get(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS"))
    to = [a.strip() for a in os.environ.get("MAIL_TO", "").split(",") if a.strip()]
    if not (host and user and pwd and to):
        present = {k: ("있음" if os.environ.get(k) else "없음")
                   for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "MAIL_TO")}
        print(f"[DRY-RUN] SMTP 미설정(상태: {present}) → 발송 대신 미리보기")
        import base64
        for cid, path in images or []:
            try:
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                html = html.replace(f"cid:{cid}", f"data:image/png;base64,{b64}")
            except Exception:
                pass
        open("/tmp/preview.html", "w", encoding="utf-8").write(html)
        return
    port = int(os.environ.get("SMTP_PORT", "465"))
    sender = os.environ.get("MAIL_FROM", user)
    root = MIMEMultipart("related") if images else MIMEMultipart("alternative")
    root["Subject"] = subject
    root["From"] = formataddr(("FSS 조기경보", sender))
    root["To"] = ", ".join(to)
    if images:
        html = _attach_inline_images(root, html, images)
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(html, "html", "utf-8"))
        root.attach(alt)
    else:
        root.attach(MIMEText(html, "html", "utf-8"))
    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
            s.login(user, pwd); s.sendmail(sender, to, root.as_string())
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls(context=ctx); s.login(user, pwd); s.sendmail(sender, to, root.as_string())
    print("메일 발송 완료 →", to)


def main():
    try:
        auth_key = os.environ["FSS_AUTH_KEY"]
        url, reg = fetch_daily_pdf_url(auth_key)
        print("PDF:", url, "| 게시:", reg)
        avg = {**SIX_MONTH_AVG, **ecos_six_month_avg()}
        d = extract(download_pdf(url), auth_key)
        an = analyze(d, avg, foreign_2m=d.get("foreign_2m"))
        print("결과:", an["result"], "|", an["summary"])
        news_html, news_images = "", []
        try:
            groups = collect_news()
            curate_and_summarize(groups)
            news_html, news_images = build_news_section(groups, date_label=an["date"])
        except Exception as ex:
            print("[NEWS] 수집/선별 전체 실패 → 기사 섹션 생략:", ex)
        subject = f"[FSS 조기경보] {an['date']} · 모니터링 결과: {an['result']} · {an['summary']}"
        send_email(subject, build_email(an, news_html), images=news_images)
    except Exception as e:
        try:
            send_email(f"[FSS 조기경보] 🛑 실패 {dt.datetime.now(KST):%Y-%m-%d}",
                       f"<p>실행 실패:</p><pre>{e}</pre>")
        finally:
            print("ERROR:", e, file=sys.stderr); sys.exit(1)


if __name__ == "__main__":
    main()
