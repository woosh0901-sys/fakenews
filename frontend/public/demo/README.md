# 가짜뉴스 판별 데모 페이지

판별기 시연을 위해 만든 **허위 기사** 정적 페이지입니다. 배포되면 아래 주소로 열립니다.

```
https://<앱주소>/demo/                         ← 목록
https://<앱주소>/demo/quantum-rumor.html       ← 양자소자 루머 (의심 / SUSPICIOUS 교차근거 0건 유보 시연용)
https://<앱주소>/demo/four-day-workweek.html   ← 주 4.5일제 (의심 / SUSPICIOUS 시연용)
https://<앱주소>/demo/power-demand.html        ← 전력수요 (가짜뉴스 / FAKE 권장 시연용)
https://<앱주소>/demo/minimum-wage.html        ← 최저임금 (가짜뉴스 / FAKE)
https://<앱주소>/demo/semiconductor.html       ← 반도체 수출 (가짜뉴스 / FAKE)
```

`vercel.json`의 `rewrites`는 파일시스템 확인 뒤에 적용되므로, 이 정적 파일들이 SPA 폴백보다 우선합니다.

## 왜 이렇게 만들었나

판정은 **비교**로 이뤄집니다. 기사를 크롤링한 뒤 실제 보도를 검색해 대조하고 Gemini가 판단합니다.
그래서 대조할 자료가 하나도 없으면 `fact_checker_by_url.py`의 다음 분기를 탑니다.

```python
if not sources:
    return {"verdict": "SUSPICIOUS", "contradiction_score": 0.8,
            "reason": "검색된 관련 신뢰 뉴스 기사가 전혀 없습니다...",
            "claims_breakdown": []}
```

즉 **완전히 지어낸 사건은 FAKE가 아니라 SUSPICIOUS로 끝나고 요소별 검증도 비어 있습니다.**
그래서 이 기사들은 전부 *실제로 보도된 사안*을 소재로 하되 **수치·발언·인과관계만 왜곡**했습니다.

## 판정에 안 걸리는 고지문

스크레이퍼는 `header`, `footer`, `nav`, `aside`를 `decompose()`로 버립니다.
그래서 "데모용 허위 기사" 고지를 `<header>`/`<footer>`에 넣으면
**사람 눈에는 보이지만 분석 대상 본문에는 들어가지 않습니다.** (검증 완료)

## 검색이 실패해도 되게 만드는 장치

`extract_news_urls_from_text()`가 **본문에 적힌 뉴스 URL을 직접 크롤링해 `sources` 맨 앞에 꽂아넣습니다.**
따라서 본문에 실제 기사 링크를 한 줄 넣어두면 검색이 0건이어도 대조 자료가 확보됩니다.

`power-demand.html`에는 이미 심어져 있습니다.

```html
<p>관련 보도 참조: https://www.seoul.co.kr/news/society/2026/08/10/20260810010007</p>
```

이 실제 기사에 **"지난 7일 최대 전력은 95.321GW", "정부는 공급 능력이 충분하다고 밝혔다"** 가 들어 있어,
데모 기사의 "300GW 돌파 / 순환단전 초읽기"와 정면으로 충돌합니다.

**다른 기사에도 적용하려면** 같은 형식의 `<p>` 한 줄을 본문에 추가하세요.
단, SNS·커뮤니티 도메인은 `EXCLUDED_DOMAINS`로 걸러지고, 링크는 크롤링 가능한(SPA가 아닌) 페이지여야 합니다.

## 시연 전 점검

1. **환경변수** — 배포 환경에 `GEMINI_API_KEY`, `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`이 설정돼 있어야 합니다.
   특히 네이버 키가 없으면 한국어 뉴스 검색이 사실상 죽고 DuckDuckGo만 남는데, 이쪽은 레이트리밋이 잦습니다.
2. **리허설 필수** — 뉴스 검색 결과는 그날그날 달라집니다. 발표 당일 아침에 한 번 돌려보세요.
3. **앵커 링크 생존 확인** — 위 seoul.co.kr 링크가 살아 있는지 확인하고, 죽었으면 최신 기사로 교체하세요.
4. **캐시 주의** — 같은 URL을 24시간 안에 다시 검사하면 `REAL` 판정만 캐시에서 즉시 반환됩니다(레포트에 `캐시` 표시).
   `FAKE`/`SUSPICIOUS`는 매번 다시 검증하므로 반복 시연에 문제없습니다.
5. **Gemini 429** — 호출이 몰리면 레이트리밋에 걸려 SUSPICIOUS 폴백이 나옵니다. 연속 시연은 간격을 두세요.
