# 🛡️ [공학경진대회 출품작] Fake News Defender
> **실시간 웹 RAG & Gemini LLM 기반 지능형 가짜뉴스 탐지 및 요소별(Claims) 팩트체크 시스템**
>
> 본 작품은 가짜뉴스의 사회적 전파 속도를 차단하기 위해 **실시간 웹/포털 검색(Naver News & DuckDuckGo)**과 **Gemini 3.5 Flash-Lite LLM**을 결합한 실시간 지능형 팩트체크 솔루션입니다. 기사·SNS·커뮤니티 루머의 사실 관계를 원본 레벨에서 교차 대조하고, 기사 내 세부 주장별 진실/거짓 분류(Claims Breakdown), 1차 공식 자료 우선순위 선별, 독립 근거 수 및 근거 품질 지표를 제공합니다.

---

## 📌 1. 작품 개요 및 문제 정의 (Problem Definition)

### 1.1. 사회적 배경 및 실제 문제점
현대 사회에서 가짜뉴스(허위 조작 정보)는 소셜 미디어(인스타그램, X)와 온라인 커뮤니티를 통해 기하급수적으로 확산됩니다. 하지만 기존의 팩트체크 방식은 다음과 같은 기술적 한계를 가집니다:
1. **LLM 환각 및 과도한 추론 의존**: 통계적 계산(출처 개수, 1차 자료 유무 등)까지 LLM에 의존할 경우 환각(Hallucination)으로 인해 부정확한 메트릭이 생성됩니다.
2. **단순 보도자료 복제 기사(Syndication) 과다 계상**: 동일한 보도자료/통신사 송고문을 수십 개 언론사가 받아쓴 경우, 이를 여러 개의 독립된 근거로 오인하여 잘못된 확신을 가질 수 있습니다.
3. **제목만 유사하고 주장이 반대인 기사 오판**: 제목은 비슷하지만 내용이 완전히 상반된 기사(예: "투자 확대" vs "투자 철회")를 제목 유사도만으로 중복 처리할 위험이 있습니다.
4. **검색 메타데이터와 실제 본문 불일치**: 낚시성 제목 기사나 스니펫만으로는 실제 기사 본문이 검증 대상과 부합하는지 정확히 판별하기 어렵습니다.
5. **보안 및 SSRF 취약성**: 사용자 입력 URL을 무분별하게 크롤링할 경우 사설망 침투(SSRF) 및 프롬프트 인젝션 위험이 존재합니다.

### 1.2. 해결 방안 (Our Approach)
본 작품은 **"Python 객관적 계산 확정 + LLM 자연어 의미 분석 제한"** 원칙 하에 **2단계 적응형 RAG-LLM 파이프라인**을 구축했습니다:
* **2단계 본문 기반 재평가 및 재정렬 (2-Stage Re-scoring & Re-ranking)**: 
  - 1차 메타데이터 점수로 상위 6개 후보를 선별한 뒤 본문을 병렬 사전 크롤링합니다.
  - 확보된 본문 내용과 핵심 사실을 융합하여 `calculate_relevance_score()`와 `priority_score`를 재계산하고 후보 순위를 재정렬합니다.
  - 본문 크롤링 실패 시 1차 점수를 안전하게 유지(Fallback)합니다.
* **본문 기반 중복 검출 및 대립 방향성 감지 (`are_articles_duplicated`)**: 
  - 기자명, 이메일, 저작권, 상투적 배포 문구를 정규화한 후 핵심 본문 유사도(`content_similarity`)와 제목 유사도를 결합 평가합니다.
  - 방향성 대립 단어(투자 vs 철회, 찬성 vs 반대, 사실무근 vs 사실 등) 감지 시 제목이 유사해도 비중복으로 분리 보존합니다.
* **1차 공식 자료(PRIMARY) 우선순위**: 정부기관(`.go.kr`), 법원, 통계청, 선관위, 전자공시(DART) 등 1차 공식 출처를 2차 언론 기사보다 최우선 대조군으로 배정하며 `primary_source_found`를 Python에서 확정합니다.
* **지능형 근거 품질 지표 (`calculate_evidence_quality`)**: 출처 가중치 평균(40%) + 독립 출처 수 비율(30%) + 도메인 다양성(15%) + 1차 공식 자료 보너스(15%)를 결합한 0.0~1.0 근거 품질 척도를 산출합니다.
* **Gemini 3.5 Flash-Lite 의미 분석 엔진**: LLM은 통계 계산이 아닌, 참고자료가 주장을 실제로 지지/반박하는지, 자료 간 상호 충돌이 있는지, Claims Breakdown 세부 요소가 진실/거짓인지 자연어 의미 분석에 집중합니다.
* **엔터프라이즈급 보안 아키텍처**: DNS Resolution 기반 SSRF 방어, IP 슬라이딩 윈도우 Rate Limiting, 외부 텍스트 격리 태그(`<UNTRUSTED_...>`) 완비.
* **뉴스 에디토리얼 대시보드 UI**: 상단 마스트헤드 롤링 티커, 기사 스캔 애니메이션, 최상단 정밀 레포트, 우측 고정 랭킹 레일, 판정별 히스토리 필터링 지원.

---

## 🏗️ 2. 시스템 아키텍처 및 파이프라인 (Architecture Flow)

```mermaid
flowchart TD
    subgraph Stage1["1. 수집 & 보안 검증"]
        A["뉴스/SNS URL 입력"] --> B["SSRF 차단 & 본문 추출"]
        B --> C["핵심 키워드 추출"]
    end

    subgraph Stage2["2. RAG 검색 & Python 2단계 재평가"]
        C --> D["하이브리드 검색 (Naver News + DDG)"]
        D --> E["상위 6개 본문 병렬 크롤링"]
        E --> F["본문 기반 2차 재평가 & 재정렬 (Re-ranking)"]
        F --> G["제목+본문 유사도 & 대립 방향성 중복 제거"]
        G --> H["Python 지표 확정 (출처수·1차자료·근거품질)"]
    end

    subgraph Stage3["3. LLM 심층 분석 & 대시보드 표출"]
        H --> I["Gemini 3.5 Flash-Lite (지지·반박·모순 의미 분석 & Claims)"]
        I --> J["Python 계산값 결합 & DB 저장"]
        J --> K["뉴스 에디토리얼 대시보드 실시간 표출"]
    end
```

---

## 📊 3. 판정 기준 및 지표 정의 (Verdict & Metrics)

### 3.1. 판정 (Verdict)
| 판정 (Verdict) | 판정 기준 및 의미 |
| :--- | :--- |
| **`REAL`** | 신뢰할 수 있는 독립된 1차 자료 또는 복수의 독립된 주요 출처와 핵심 사실(수치, 인물, 발언, 사건 여부)이 명백히 일치하는 경우 |
| **`FAKE`** | 공신력 있는 근거에 의해 핵심 사실이 날조·조작되었거나 명백한 허위 왜곡임이 입증된 경우 |
| **`SUSPICIOUS`** | 근거가 부족하여 사실 확인이 어렵거나, 1차 자료와 보도가 충돌하거나, 과장·루머가 섞여 있어 단정하기 어려운 경우 (*검색 결과가 없거나 부족해도 FAKE로 단정하지 않고 SUSPICIOUS 부여*) |

### 3.2. 정량적 지표 정의 (Python 확정)
* **`contradiction_score` (0.0 ~ 1.0)**: 모순도/불일치 정도 (0.0=완전일치, 1.0=완전모순, *진실 확률이 아님*).
* **`evidence_quality` (0.0 ~ 1.0)**: 확보된 교차 검증 근거의 완전성/독립성/다양성 품질 척도 (*Python에서 가중 결합 산출*).
* **`independent_source_count` (정수)**: 동일 보도자료 전재를 단일 출처로 묶은 실제 독립 원출처 개수 (*Python에서 확정 산출*).
* **`primary_source_found` (Boolean)**: 정부/공공기관/법원 등 공식 1차 자료 포함 여부 (*Python에서 확정 산출*).

---

## 🛡️ 4. 엔터프라이즈 보안 및 회복 탄력성 (Security & Resilience)

* **SSRF (Server-Side Request Forgery) 완벽 방어**:
  - 사용자 입력 URL의 DNS Resolution을 수행하여 사설망(`10.0.0.0/8`, `192.168.0.0/16`, `172.16.0.0/12`), 루프백(`127.0.0.1`, `::1`), 클라우드 메타데이터(`169.254.169.254`) 원천 차단.
  - 리다이렉트 발생 시 매 Hop마다 대상 IP를 재검증하여 Redirect SSRF 차단.
* **IP 기반 슬라이딩 윈도우 Rate Limiting**:
  - `/api/check`: 1분당 최대 5회
  - `/api/preview`: 1분당 최대 10회
  - `/api/chat`: 1분당 최대 10회
  - 댓글/리액션: 1분당 최대 20~30회
* **프롬프트 인젝션(Prompt Injection) 격리**:
  - 외부 기사 및 참고자료를 `<UNTRUSTED_TARGET_ARTICLE>`, `<UNTRUSTED_REFERENCE_SOURCE>` 태그로 격리.
* **Gemini 429 Fail-Fast & DB 오염 방지**:
  - 외부 API 분당 할당량 초과 시 불필요한 재시도를 중단하고, `transient_error: True` 플래그로 임시 유보 결과가 DB에 오염 저장되지 않도록 방어.

---

## 📂 5. 프로젝트 구조 (Project Structure)

```text
.
├── backend_app.py               # FastAPI 백엔드 서버 (Rate Limiter, CORS, 캐싱, 보안 헤더, Q&A/챗봇 API)
├── fact_checker_by_url.py       # RAG 파이프라인, 2단계 본문 재평가, 출처 선별, LLM 교차 검증
├── security_utils.py            # SSRF 방어, 안전한 HTTP 요청, 데이터 살균, Gemini 스키마 검증 모듈
├── naver_news_api.py            # 환경변수 로드 및 네이버 뉴스 검색 API
├── test_security.py             # SSRF, Rate Limit, 보안 헤더 등 보안 단위 테스트 (9개)
├── test_rag_pipeline.py         # 본문 재평가, 중복제거, 1차자료 우선, 근거품질 단위 테스트 (14개)
├── test_backend_and_llm.py      # 백엔드 API, 상호 모순 처리, 메트릭 불변성 통합 테스트 (3개)
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # 뉴스 에디토리얼 대시보드 메인
│   │   ├── Landing.jsx          # 마스트헤드 티커 & 분석 스캔 로딩 화면
│   │   ├── verdict.js           # 판정별 UI 톤 & 색상 정의
│   │   ├── useNarrow.js         # 모바일 반응형 뷰포트 훅
│   │   └── index.css            # Helvetica/SUIT 폰트 & 애니메이션 스타일
│   └── public/demo/             # 시연용 데모 가짜뉴스 HTML 페이지 4종
├── requirements.txt             # Python 의존성
└── vercel.json                  # Vercel 배포 및 라우팅 설정
```

---

## 🚀 6. 설치 및 실행 방법 (Getting Started)

### 6.1. 데이터베이스 테이블 스키마 생성
Supabase 웹 콘솔 **SQL Editor**에 아래 DDL 스크립트를 붙여넣어 테이블 및 외래키 제약조건을 초기화합니다.
```sql
CREATE TABLE checks (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    verdict TEXT NOT NULL,
    contradiction_score REAL NOT NULL,
    nll_loss REAL,
    reason TEXT NOT NULL,
    stage INTEGER NOT NULL DEFAULT 1,
    claims_breakdown JSONB, -- 요소별 개별 진실/거짓 판정 데이터
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE check_references (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    check_id BIGINT REFERENCES checks(id) ON DELETE CASCADE NOT NULL,
    title TEXT NOT NULL,
    link TEXT NOT NULL,
    description TEXT NOT NULL,
    pub_date TEXT NOT NULL
);

CREATE TABLE check_comments (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    check_id BIGINT REFERENCES checks(id) ON DELETE CASCADE NOT NULL,
    author TEXT NOT NULL DEFAULT '익명',
    content TEXT NOT NULL,
    user_token TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE check_reactions (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    check_id BIGINT REFERENCES checks(id) ON DELETE CASCADE NOT NULL,
    emoji TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    UNIQUE (check_id, emoji)
);

ALTER TABLE checks DISABLE ROW LEVEL SECURITY;
ALTER TABLE check_references DISABLE ROW LEVEL SECURITY;
ALTER TABLE check_comments DISABLE ROW LEVEL SECURITY;
ALTER TABLE check_reactions DISABLE ROW LEVEL SECURITY;
```

### 6.2. 환경 변수 설정 (`.env`)
프로젝트 루트 폴더에 `.env` 파일을 생성하고 아래 양식에 맞추어 API 키를 입력합니다.
```ini
NAVER_CLIENT_ID=여러분의_네이버_클라이언트_ID
NAVER_CLIENT_SECRET=여러분의_네이버_클라이언트_SECRET
GEMINI_API_KEY=여러분의_GEMINI_API_KEY
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-or-service-role-key
```

### 6.3. 백엔드 실행
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
python backend_app.py
```

### 6.4. 프론트엔드 실행
```bash
cd frontend
npm install
npm run dev
```
웹 브라우저로 `http://localhost:5173`에 접속하여 실시간 대시보드 시연을 진행합니다.

---

## 🧪 7. 자동화 테스트 실행 (Test Suites)

총 **26개 단위 및 통합 테스트**로 파이프라인 무결성을 상시 검증합니다:

```bash
# 전체 테스트 스위트 (26개 단위/통합 테스트) 실행
python -m unittest test_security.py test_rag_pipeline.py test_backend_and_llm.py

# 개별 테스트 실행
python test_security.py       # SSRF 방어, Rate Limit, 보안 헤더, 살균 등 9개 테스트
python test_rag_pipeline.py   # 본문 재평가, 중복제거, 1차자료 우선, 근거품질 산출 등 14개 테스트
python test_backend_and_llm.py # 백엔드 API, 상호 모순 처리, 메트릭 불변성 등 3개 테스트
```
