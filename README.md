# FSS-Monitoring

금융감독원 **일일 금융시장 동향** 기반 통합 조기경보지표를 매 영업일 자동 산출하여 메일로 발송합니다.
추가로 **삼성그룹 신문스크랩**(주요 국내 계열사 매거진형 카드)을 같은 메일에 덧붙여 발송합니다.

## 기능

1. **통합 조기경보지표 모니터링** — 주가(KOSPI)·환율·금리(국고3년)·ROK CDS·신용스프레드 5개 지표를
   트리거 기준과 비교해 위기 단계(정상 / 1단계 / 2단계)를 판정.
2. **삼성그룹 신문스크랩** — 주요 국내 계열사 기사를 그룹별 카드(고정 일러스트 배너 + 카테고리 태그 +
   기사 3건)로 매거진처럼 한 장에 정리.
   - 대상 그룹: 삼성전자 · 전자계열(SDI·전기·SDS) · 바이오·물산 · 금융(생명·화재·증권·카드) · 기타 국내 계열사(중공업·E&A·호텔신라·제일기획·에스원)
   - 수집 소스: **네이버 뉴스 API 우선**, 미설정·실패 시 **구글뉴스 RSS로 자동 폴백**
   - 수집 구간: **전(영업)일 07:11 ~ 금일 07:11 KST** (월요일은 금요일 07:11부터 — 주말 포함)
   - 같은 사안 기사를 묶어 **보도량(다룬 언론사 수)** 산출 → 보도량·중요도 기준으로
     **Claude API가 카테고리별 3건 선별 + 한 줄 요약 + 언론사 약칭** 생성
     (`ANTHROPIC_API_KEY` 미설정 시 보도량순 상위 3건, 제목만 표시)
   - 카드 배너 이미지는 `assets/news/*.png` 고정 사용(메일에 CID 인라인 첨부). 직접 만든 일러스트로
     같은 파일명 교체 가능. 재생성: `python scripts/gen_news_images.py`

## 환경 변수 / GitHub Secrets

| 변수 | 용도 | 필수 |
|---|---|---|
| `FSS_AUTH_KEY` | 금융감독원 OpenAPI 인증키 | ✅ |
| `ECOS_KEY` | 한국은행 ECOS (6개월 평균 자동계산) | 선택 |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` | 메일 발송 | ✅ |
| `MAIL_TO` / `MAIL_FROM` | 수신/발신 주소 | ✅ |
| `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | 네이버 뉴스 검색 API | 선택(미설정 시 구글뉴스 RSS 사용) |
| `ANTHROPIC_API_KEY` | 기사 한 줄 요약(Claude API) | 선택(미설정 시 제목만 표시) |

> 네이버 키는 네이버 **개발자센터**(developers.naver.com)에서 "검색" API 애플리케이션을 등록하면 발급되는
> Client ID/Secret 입니다. 네이버 로그인 계정·비밀번호가 아닙니다.

### 신문스크랩 튜닝(선택)
- `NEWS_PER_KEYWORD` (기본 6) — 키워드당 수집 후보 수
- `NEWS_PER_GROUP` (기본 3) — 카드(그룹)당 최종 표시 기사 수
- `NEWS_CANDIDATES` (기본 8) — 그룹당 AI 선별에 넘길 후보 수
- `NEWS_SUMMARY_MODEL` (기본 `claude-opus-4-8`) — 선별·요약 모델(예: `claude-haiku-4-5`로 비용 절감)

## 실행

```bash
pip install -r requirements.txt
python fss_monitor.py
```

SMTP 미설정 시 발송 대신 `/tmp/preview.html`에 미리보기를 저장합니다.
GitHub Actions로 매 영업일 07:11 KST에 자동 실행됩니다(`.github/workflows/main.yml`).
