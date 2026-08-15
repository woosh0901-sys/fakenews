import os
import sys
import httpx
import urllib.parse
import re
import time
import threading
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

# Import our RAG pipeline, credentials and security utilities
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from fact_checker_by_url import check_url_validity, GeminiRateLimitError
from naver_news_api import SUPABASE_URL, SUPABASE_KEY, NAVER_CLIENT_ID
from security_utils import validate_url_safe, sanitize_text, MAX_URL_LENGTH

# Clean SUPABASE_URL to make sure it doesn't end with /rest/v1 or /rest/v1/ (prevent path doubling)
if SUPABASE_URL:
    SUPABASE_URL = SUPABASE_URL.strip()
    if SUPABASE_URL.endswith("/rest/v1"):
        SUPABASE_URL = SUPABASE_URL[:-8]
    elif SUPABASE_URL.endswith("/rest/v1/"):
        SUPABASE_URL = SUPABASE_URL[:-9]
    if SUPABASE_URL.endswith("/"):
        SUPABASE_URL = SUPABASE_URL[:-1]

# 히스토리 목록에 노출할 최신 검증 개수. 데이터는 지우지 않고 조회만 제한하므로
# 통계·랭킹의 누적 집계에는 영향을 주지 않는다.
HISTORY_LIMIT = 25

SUPABASE_ENABLED = bool(SUPABASE_URL and SUPABASE_KEY and SUPABASE_URL != "여기에_프로젝트_URL_입력")
if not SUPABASE_ENABLED:
    print("[-] 알림: Supabase URL 또는 API Key가 설정되지 않았습니다. 결과 저장 및 히스토리/통계 기능이 비활성화됩니다.")

IS_PRODUCTION = bool(os.environ.get("VERCEL") or os.environ.get("ENVIRONMENT") == "production")

# FastAPI App Configuration (Disable API docs in production to prevent structure exposure)
app = FastAPI(
    title="Fake News Defender Backend API",
    version="1.0.0",
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json"
)

# -------------------------------------------------------------
# 1. CORS Setup
# -------------------------------------------------------------
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://fakenews-one-pied.vercel.app"
]
custom_origin = os.environ.get("ALLOWED_ORIGIN")
if custom_origin:
    ALLOWED_ORIGINS.extend([o.strip() for o in custom_origin.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if IS_PRODUCTION else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# -------------------------------------------------------------
# 2. Security Headers Middleware
# -------------------------------------------------------------
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response

# -------------------------------------------------------------
# 3. Thread-Safe IP Rate Limiter (Sliding Window)
# -------------------------------------------------------------
class InMemoryRateLimiter:
    """
    메모리 기반 슬라이딩 윈도우 Rate Limiter.
    IP별 요청 빈도를 체크하여 API 자원 고갈 및 DDoS/Brute-force를 방어합니다.
    """
    def __init__(self):
        self._requests = defaultdict(list)
        self._lock = threading.Lock()

    def is_rate_limited(self, ip: str, limit: int, window_seconds: int = 60) -> bool:
        now = time.time()
        with self._lock:
            timestamps = self._requests[ip]
            valid_timestamps = [t for t in timestamps if now - t < window_seconds]
            if len(valid_timestamps) >= limit:
                self._requests[ip] = valid_timestamps
                return True
            valid_timestamps.append(now)
            self._requests[ip] = valid_timestamps
            return False

rate_limiter = InMemoryRateLimiter()

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

def check_rate_limit(request: Request, limit: int, window_seconds: int = 60, endpoint_name: str = "API"):
    client_ip = get_client_ip(request)
    key = f"{client_ip}:{endpoint_name}"
    if rate_limiter.is_rate_limited(key, limit=limit, window_seconds=window_seconds):
        raise HTTPException(
            status_code=429,
            detail=f"단시간 내에 너무 많은 요청이 발생했습니다 ({limit}회/{window_seconds}초 초과). 잠시 후 다시 시도해 주세요."
        )

# Helper function to get Supabase API headers
def get_supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

class CheckRequest(BaseModel):
    url: str = Field(..., max_length=MAX_URL_LENGTH)

class CommentRequest(BaseModel):
    author: str = Field(default="익명", max_length=30)
    content: str = Field(..., min_length=1, max_length=1000)
    user_token: Optional[str] = Field(default=None, max_length=64)


@app.post("/api/preview")
async def preview_article(payload: CheckRequest, request: Request):
    """
    분석 로딩 화면용 경량 미리보기.
    (Rate limit: 분당 10회, SSRF 방어 적용)
    """
    check_rate_limit(request, limit=10, window_seconds=60, endpoint_name="preview")
    
    url = payload.url.strip()
    is_safe, err_msg = validate_url_safe(url)
    if not is_safe:
        raise HTTPException(status_code=400, detail=f"안전하지 않거나 허용되지 않는 URL 형식입니다: {err_msg}")

    try:
        from fact_checker_by_url import (
            is_instagram_url, is_twitter_url,
            scrape_instagram_post, scrape_twitter_post, scrape_url_content,
        )

        if is_instagram_url(url):
            article, source = scrape_instagram_post(url), "인스타그램"
        elif is_twitter_url(url):
            article, source = scrape_twitter_post(url), "X(트위터)"
        else:
            article = scrape_url_content(url)
            source = (article or {}).get("source") or ""

        if not article or not article.get("content"):
            raise HTTPException(status_code=422, detail="기사 또는 게시글의 본문을 추출할 수 없습니다.")

        return {
            "title": sanitize_text(article.get("title", ""), max_length=300),
            "content": sanitize_text(article.get("content", ""), max_length=4000),
            "source": sanitize_text(source, max_length=100),
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[-] 미리보기 추출 에러: {e}")
        raise HTTPException(status_code=500, detail="미리보기 데이터를 불러오는 중 오류가 발생했습니다.")


@app.post("/api/check")
async def check_url(payload: CheckRequest, request: Request):
    """
    팩트체크 분석 실행 엔드포인트.
    (Rate limit: 분당 5회, SSRF 방어, 악의적 URL 차단, 캐시 적용)
    """
    check_rate_limit(request, limit=5, window_seconds=60, endpoint_name="check")

    url = payload.url.strip()
    is_safe, err_msg = validate_url_safe(url)
    if not is_safe:
        raise HTTPException(status_code=400, detail=f"안전하지 않거나 허용되지 않는 URL 형식입니다: {err_msg}")
        
    # 24시간 내 동일 URL에 대한 캐시가 있는지 먼저 확인하여 API 호출 횟수를 아낍니다.
    if SUPABASE_ENABLED:
        try:
            time_limit = (datetime.utcnow() - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
            cache_query_url = f"{SUPABASE_URL}/rest/v1/checks"
            cache_params = {
                "select": "*,sources:check_references(*)",
                "url": f"eq.{url}",
                "created_at": f"gte.{time_limit}",
                "order": "created_at.desc",
                "limit": "1"
            }
            headers = get_supabase_headers()
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                cache_resp = await client.get(cache_query_url, headers=headers, params=cache_params)
                if cache_resp.status_code == 200:
                    cache_data = cache_resp.json()
                    if cache_data and len(cache_data) > 0:
                        cache_item = cache_data[0]
                        if cache_item.get("verdict") == "REAL":
                            print(f"[★] 동일 URL에 대한 최근 24시간 내 '진실(REAL)' 캐시된 검사 결과가 있어 DB에서 즉시 반환합니다: {url}")
                            
                            raw_sources = cache_item.get("sources") or []
                            formatted_sources = []
                            for s in raw_sources:
                                formatted_sources.append({
                                    "title": s.get("title"),
                                    "link": s.get("link"),
                                    "description": s.get("description"),
                                    "pubDate": s.get("pub_date")
                                })
                                
                            result = {
                                "id": cache_item.get("id"),
                                "verdict": cache_item.get("verdict"),
                                "contradiction_score": cache_item.get("contradiction_score"),
                                "nll_loss": cache_item.get("nll_loss"),
                                "reason": cache_item.get("reason"),
                                "stage": cache_item.get("stage"),
                                "target_title": cache_item.get("title"),
                                "target_url": cache_item.get("url"),
                                "claims_breakdown": cache_item.get("claims_breakdown") or [],
                                "sources": formatted_sources,
                                "cached": True
                            }
                            return result
                        else:
                            print(f"[*] 캐시된 기록이 있으나 판정이 {cache_item.get('verdict')}이므로 실시간 재검증을 진행합니다: {url}")
        except Exception as cache_err:
            print(f"[-] 캐시 조회 오류 (정상 파이프라인으로 진행): {cache_err}")
            
    try:
        result = await run_in_threadpool(check_url_validity, url)
        if not result:
            raise HTTPException(status_code=500, detail="기사 본문 크롤링에 실패했거나 안전하지 않은 페이지입니다.")
            
        result['id'] = None
        if SUPABASE_ENABLED:
            if result.get("transient_error"):
                print("[*] 일시적 API 오류(429 등)로 판정된 결과이므로 Supabase 저장을 건너뜁니다.")
            else:
                try:
                    headers = get_supabase_headers()

                    # Insert into checks table
                    check_data = {
                        "url": result['target_url'],
                        "title": result['target_title'],
                        "verdict": result['verdict'],
                        "contradiction_score": float(result['contradiction_score']),
                        "nll_loss": float(result['nll_loss']) if result.get('nll_loss') is not None else None,
                        "reason": result['reason'],
                        "stage": int(result['stage'])
                    }
                    if 'claims_breakdown' in result:
                        check_data['claims_breakdown'] = result['claims_breakdown']

                    async with httpx.AsyncClient(timeout=15.0) as client:
                        resp = await client.post(f"{SUPABASE_URL}/rest/v1/checks", headers=headers, json=check_data)
                        if resp.status_code != 201:
                            # Fallback: if 'claims_breakdown' column doesn't exist yet in checks table, retry without it
                            if 'claims_breakdown' in check_data:
                                print("[!] Warning: 'claims_breakdown' column might be missing. Retrying insert without it...")
                                del check_data['claims_breakdown']
                                resp = await client.post(f"{SUPABASE_URL}/rest/v1/checks", headers=headers, json=check_data)
                                if resp.status_code != 201:
                                    raise Exception(f"Supabase checks 저장 실패 (HTTP {resp.status_code})")
                            else:
                                raise Exception(f"Supabase checks 저장 실패 (HTTP {resp.status_code})")

                        inserted_check = resp.json()[0]
                        check_id = inserted_check['id']

                        # Insert references if present
                        ref_data = []
                        for s in result.get('sources', []):
                            ref_data.append({
                                "check_id": check_id,
                                "title": s.get('title', ''),
                                "link": s.get('link', ''),
                                "description": s.get('description', ''),
                                "pub_date": s.get('pubDate') or s.get('pub_date', '')
                            })

                        if ref_data:
                            resp_ref = await client.post(f"{SUPABASE_URL}/rest/v1/check_references", headers=headers, json=ref_data)
                            if resp_ref.status_code != 201:
                                print(f"[-] check_references 저장 실패: HTTP {resp_ref.status_code}")

                        result['id'] = check_id
                except Exception as db_err:
                    print(f"[-] 검사 결과 저장 실패: {db_err}")
                    result['warning'] = "검사는 완료되었으나 데이터베이스 저장이 일시적으로 실패했습니다."
        else:
            result['warning'] = "데이터베이스 설정이 없어 결과가 저장되지 않았습니다."

        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[-] 탐지 분석 중 예외 발생: {e}")
        raise HTTPException(status_code=500, detail="탐지 분석 중 기술적 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")

@app.get("/api/history")
async def get_history(request: Request):
    """최근 검증 기록 조회 (Rate limit: 분당 60회, 최신 HISTORY_LIMIT건만 반환)"""
    check_rate_limit(request, limit=60, window_seconds=60, endpoint_name="history")
    if not SUPABASE_ENABLED:
        return []
    try:
        headers = get_supabase_headers()
        # Fetch checks joining with check_references as 'sources' sorting by created_at desc.
        # 최신 HISTORY_LIMIT건만 내려준다. 행 자체는 지우지 않으므로 /api/stats 와
        # /api/stats/rankings 의 누적 집계는 그대로 유지된다.
        url = (
            f"{SUPABASE_URL}/rest/v1/checks?select=*,sources:check_references(*)"
            f"&order=created_at.desc&limit={HISTORY_LIMIT}"
        )
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                raise Exception(f"Supabase history 조회 실패 (HTTP {resp.status_code})")
            return resp.json()
    except Exception as e:
        print(f"[-] 히스토리 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="히스토리 목록을 불러오는 중 오류가 발생했습니다.")

@app.delete("/api/history/{check_id}")
async def delete_history_item(check_id: int, request: Request):
    """검증 기록 삭제"""
    check_rate_limit(request, limit=30, window_seconds=60, endpoint_name="delete_history")
    if not SUPABASE_ENABLED:
        raise HTTPException(status_code=503, detail="데이터베이스 기능이 비활성화되어 있습니다.")
    try:
        headers = get_supabase_headers()
        url = f"{SUPABASE_URL}/rest/v1/checks?id=eq.{check_id}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.delete(url, headers=headers)
            if resp.status_code not in (200, 204):
                raise Exception(f"Supabase 삭제 실패 (HTTP {resp.status_code})")
            return {"status": "success", "message": "성공적으로 삭제되었습니다."}
    except Exception as e:
        print(f"[-] 기록 삭제 오류: {e}")
        raise HTTPException(status_code=500, detail="기록 삭제 중 오류가 발생했습니다.")

@app.get("/api/stats")
async def get_stats(request: Request):
    """종합 통계 집계 조회 (Rate limit: 분당 60회)"""
    check_rate_limit(request, limit=60, window_seconds=60, endpoint_name="stats")
    if not SUPABASE_ENABLED:
        return {
            "total_checks": 0,
            "real_count": 0,
            "fake_count": 0,
            "suspicious_count": 0,
            "avg_nll": 0.0,
            "avg_contradiction_score": 0.0
        }
    try:
        headers = get_supabase_headers()
        url = f"{SUPABASE_URL}/rest/v1/checks?select=verdict,nll_loss,contradiction_score"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                raise Exception(f"Supabase stats 조회 실패 (HTTP {resp.status_code})")
            
            rows = resp.json()
            total_checks = len(rows)
            
            if total_checks == 0:
                return {
                    "total_checks": 0,
                    "real_count": 0,
                    "fake_count": 0,
                    "suspicious_count": 0,
                    "avg_nll": 0.0,
                    "avg_contradiction_score": 0.0
                }
                
            real_count = 0
            fake_count = 0
            suspicious_count = 0
            total_nll = 0.0
            nll_count = 0
            total_score = 0.0
            
            for row in rows:
                verdict = row.get("verdict")
                if verdict == "REAL":
                    real_count += 1
                elif verdict == "FAKE":
                    fake_count += 1
                else:
                    suspicious_count += 1
                    
                nll = row.get("nll_loss")
                if nll is not None:
                    try:
                        total_nll += float(nll)
                        nll_count += 1
                    except (ValueError, TypeError):
                        pass
                    
                try:
                    total_score += float(row.get("contradiction_score") or 0.0)
                except (ValueError, TypeError):
                    pass
                
            return {
                "total_checks": total_checks,
                "real_count": real_count,
                "fake_count": fake_count,
                "suspicious_count": suspicious_count,
                "avg_nll": round(total_nll / nll_count, 4) if nll_count > 0 else 0.0,
                "avg_contradiction_score": round(total_score / total_checks, 4)
            }
    except Exception as e:
        print(f"[-] 통계 집계 오류: {e}")
        raise HTTPException(status_code=500, detail="통계 데이터를 불러오는 중 오류가 발생했습니다.")

@app.get("/api/stats/rankings")
async def get_rankings(request: Request):
    """최다 검증 및 허위 의심 순위 (Rate limit: 분당 60회)"""
    check_rate_limit(request, limit=60, window_seconds=60, endpoint_name="rankings")
    if not SUPABASE_ENABLED:
        return {"most_checked": [], "top_fakes": []}
    try:
        headers = get_supabase_headers()
        url = f"{SUPABASE_URL}/rest/v1/checks?select=url,title,verdict,contradiction_score,created_at&limit=500"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                raise Exception(f"Supabase checks 조회 실패 (HTTP {resp.status_code})")
            rows = resp.json()
        
        from collections import Counter
        url_counts = Counter()
        url_titles = {}
        for r in rows:
            u = r.get('url', '')
            if not u:
                continue
            url_counts[u] += 1
            r_created = r.get('created_at') or ''
            if u not in url_titles or r_created > url_titles[u].get('created_at', ''):
                url_titles[u] = {'title': r.get('title', '제목 없음'), 'created_at': r_created}
                
        most_checked = []
        for u, count in url_counts.most_common(5):
            most_checked.append({
                "url": u,
                "title": url_titles[u]['title'],
                "count": count
            })
            
        fakes = [r for r in rows if r.get('verdict') in ('FAKE', 'SUSPICIOUS')]
        fakes.sort(key=lambda x: float(x.get('contradiction_score') or 0.0), reverse=True)
        
        top_fakes = []
        seen_urls = set()
        for f in fakes:
            u = f.get('url', '')
            if u and u not in seen_urls:
                seen_urls.add(u)
                top_fakes.append({
                    "url": u,
                    "title": f.get('title', '제목 없음'),
                    "contradiction_score": f.get('contradiction_score', 0.0),
                    "verdict": f.get('verdict', 'SUSPICIOUS')
                })
                if len(top_fakes) >= 5:
                    break
                    
        return {
            "most_checked": most_checked,
            "top_fakes": top_fakes
        }
    except Exception as e:
        print(f"[-] 랭킹 집계 오류: {e}")
        raise HTTPException(status_code=500, detail="랭킹 데이터를 불러오는 중 오류가 발생했습니다.")

@app.get("/api/history/{check_id}/comments")
async def get_comments(check_id: int, request: Request):
    """댓글 목록 조회 (Rate limit: 분당 60회)"""
    check_rate_limit(request, limit=60, window_seconds=60, endpoint_name="get_comments")
    if not SUPABASE_ENABLED:
        return []
    try:
        headers = get_supabase_headers()
        url = f"{SUPABASE_URL}/rest/v1/check_comments?check_id=eq.{check_id}&order=created_at.asc"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                raise Exception(f"Supabase 댓글 조회 실패 (HTTP {resp.status_code})")
            return resp.json()
    except Exception as e:
        print(f"[-] 댓글 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="댓글을 불러오는 중 오류가 발생했습니다.")

@app.post("/api/history/{check_id}/comments")
async def add_comment(check_id: int, payload: CommentRequest, request: Request):
    """댓글 등록 (Rate limit: 분당 10회, XSS/입력값 살균 적용)"""
    check_rate_limit(request, limit=10, window_seconds=60, endpoint_name="add_comment")
    
    author = sanitize_text(payload.author, max_length=30) or "익명"
    content = sanitize_text(payload.content, max_length=1000)
    user_token = sanitize_text(payload.user_token or "", max_length=64) or None
    
    if not content:
        raise HTTPException(status_code=400, detail="유효한 댓글 내용을 입력해 주세요.")
        
    if not SUPABASE_ENABLED:
        raise HTTPException(status_code=503, detail="데이터베이스 기능이 비활성화되어 있습니다.")
        
    try:
        headers = get_supabase_headers()
        comment_data = {
            "check_id": check_id,
            "author": author,
            "content": content,
            "user_token": user_token
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{SUPABASE_URL}/rest/v1/check_comments", headers=headers, json=comment_data)
            if resp.status_code != 201:
                raise Exception(f"Supabase 댓글 저장 실패 (HTTP {resp.status_code})")
            return resp.json()[0]
    except Exception as e:
        print(f"[-] 댓글 등록 오류: {e}")
        raise HTTPException(status_code=500, detail="댓글을 저장하는 중 오류가 발생했습니다.")

@app.delete("/api/history/{check_id}/comments/{comment_id}")
async def delete_comment(check_id: int, comment_id: int, user_token: str, request: Request):
    """댓글 삭제 (본인 인증 토큰 일치 검증)"""
    check_rate_limit(request, limit=20, window_seconds=60, endpoint_name="delete_comment")
    if not SUPABASE_ENABLED:
        raise HTTPException(status_code=503, detail="데이터베이스 기능이 비활성화되어 있습니다.")
        
    try:
        headers = get_supabase_headers()
        url = f"{SUPABASE_URL}/rest/v1/check_comments?id=eq.{comment_id}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp_get = await client.get(url, headers=headers)
            if resp_get.status_code != 200 or not resp_get.json():
                raise HTTPException(status_code=404, detail="댓글을 찾을 수 없거나 이미 삭제되었습니다.")
                
            comment = resp_get.json()[0]
            db_token = comment.get("user_token")
            
            # 본인 토큰 검증
            if db_token and db_token != user_token.strip():
                raise HTTPException(status_code=403, detail="본인이 작성한 댓글만 삭제할 수 있습니다.")
                
            del_url = f"{SUPABASE_URL}/rest/v1/check_comments?id=eq.{comment_id}"
            resp_del = await client.delete(del_url, headers=headers)
            if resp_del.status_code not in (200, 204):
                raise Exception(f"Supabase 댓글 삭제 실패 (HTTP {resp_del.status_code})")
                
            return {"status": "success", "message": "댓글이 삭제되었습니다."}
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"[-] 댓글 삭제 오류: {e}")
        raise HTTPException(status_code=500, detail="댓글 삭제 중 오류가 발생했습니다.")

class ReactionRequest(BaseModel):
    emoji: str = Field(..., max_length=10)
    is_canceling: bool = False

@app.get("/api/history/{check_id}/reactions")
async def get_reactions(check_id: int, request: Request):
    """리액션 통계 조회 (Rate limit: 분당 60회)"""
    check_rate_limit(request, limit=60, window_seconds=60, endpoint_name="get_reactions")
    if not SUPABASE_ENABLED:
        return []
    try:
        headers = get_supabase_headers()
        url = f"{SUPABASE_URL}/rest/v1/check_reactions?check_id=eq.{check_id}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                raise Exception(f"Supabase 리액션 조회 실패 (HTTP {resp.status_code})")
            return resp.json()
    except Exception as e:
        print(f"[-] 리액션 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="리액션 데이터를 불러오는 중 오류가 발생했습니다.")

@app.post("/api/history/{check_id}/reactions")
async def add_reaction(check_id: int, payload: ReactionRequest, request: Request):
    """이모지 리액션 등록 및 취소 (Rate limit: 분당 30회)"""
    check_rate_limit(request, limit=30, window_seconds=60, endpoint_name="add_reaction")
    emoji = sanitize_text(payload.emoji, max_length=10)
    if not emoji or emoji not in ("👍", "👎", "😮", "😡"):
        raise HTTPException(status_code=400, detail="허용되지 않는 이모지입니다.")
        
    if not SUPABASE_ENABLED:
        raise HTTPException(status_code=503, detail="데이터베이스 기능이 비활성화되어 있습니다.")
        
    try:
        headers = get_supabase_headers()
        url = f"{SUPABASE_URL}/rest/v1/check_reactions?check_id=eq.{check_id}&emoji=eq.{urllib.parse.quote(emoji)}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp_get = await client.get(url, headers=headers)
            existing = resp_get.json() if resp_get.status_code == 200 else []
            
            if existing and len(existing) > 0:
                curr_count = existing[0].get("count", 1)
                new_count = max(0, curr_count - 1) if payload.is_canceling else curr_count + 1
                patch_url = f"{SUPABASE_URL}/rest/v1/check_reactions?id=eq.{existing[0]['id']}"
                resp_patch = await client.patch(patch_url, headers=headers, json={"count": new_count})
                if resp_patch.status_code not in (200, 204):
                    raise Exception(f"리액션 업데이트 실패 (HTTP {resp_patch.status_code})")
                return {"emoji": emoji, "count": new_count}
            else:
                new_count = 0 if payload.is_canceling else 1
                resp_post = await client.post(
                    f"{SUPABASE_URL}/rest/v1/check_reactions",
                    headers=headers,
                    json={"check_id": check_id, "emoji": emoji, "count": new_count}
                )
                if resp_post.status_code != 201:
                    raise Exception(f"리액션 저장 실패 (HTTP {resp_post.status_code})")
                return {"emoji": emoji, "count": new_count}
    except Exception as e:
        print(f"[-] 리액션 처리 오류: {e}")
        raise HTTPException(status_code=500, detail="리액션 처리 중 오류가 발생했습니다.")

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)

@app.post("/api/check/{check_id}/query")
async def query_check_report(check_id: int, payload: QueryRequest, request: Request):
    """기사 정밀 진단 레포트 대상 Q&A 질문 답변 (Rate limit: 분당 10회)"""
    check_rate_limit(request, limit=10, window_seconds=60, endpoint_name="query_check")
    user_query = sanitize_text(payload.query, max_length=500)
    if not user_query:
        raise HTTPException(status_code=400, detail="질문을 입력해 주세요.")
        
    if not SUPABASE_ENABLED:
        raise HTTPException(status_code=503, detail="데이터베이스 기능이 비활성화되어 있습니다.")
        
    try:
        headers = get_supabase_headers()
        url = f"{SUPABASE_URL}/rest/v1/checks?id=eq.{check_id}&select=*,sources:check_references(*)"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200 or not resp.json():
                raise HTTPException(status_code=404, detail="검증 기록을 찾을 수 없습니다.")
            check_data = resp.json()[0]
            
        sources_text = "\n".join([
            f"- [{s.get('title')}] {s.get('description', '')}"
            for s in (check_data.get("sources") or [])
        ])
        
        prompt = (
            "당신은 팩트체크 검증 시스템의 AI 어시스턴트입니다.\n"
            f"검증 기사 제목: {check_data.get('title')}\n"
            f"판정 결과: {check_data.get('verdict')} (모순율: {check_data.get('contradiction_score')})\n"
            f"종합 소견: {check_data.get('reason')}\n"
            f"참고 자료 목록:\n{sources_text}\n\n"
            f"사용자 추가 질문: {user_query}\n\n"
            "위 사실 관계와 참고 자료를 바탕으로 사용자의 질문에 대해 명확하고 논리정연하게 답변해 주세요."
        )
        
        from fact_checker_by_url import call_gemini_api
        answer = await run_in_threadpool(call_gemini_api, prompt)
        if not answer:
            answer = "현재 AI 답변을 생성할 수 없습니다. 잠시 후 다시 질문해 주세요."
            
        return {"answer": answer}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[-] Q&A 분석 에러: {e}")
        raise HTTPException(status_code=500, detail="Q&A 답변 생성 중 오류가 발생했습니다.")

@app.post("/api/chat")
async def assistant_chat(payload: QueryRequest, request: Request):
    """AI 팩트체크 자유 질문 챗봇 (Rate limit: 분당 10회, 실시간 웹 검색 연동)"""
    check_rate_limit(request, limit=10, window_seconds=60, endpoint_name="chat")
    user_query = sanitize_text(payload.query, max_length=500)
    if not user_query:
        raise HTTPException(status_code=400, detail="질문 내용을 입력해 주세요.")
        
    try:
        from fact_checker_by_url import fetch_hybrid_news, call_gemini_api, extract_keywords_fast
        
        # 1. 키워드 추출 및 실시간 하이브리드 웹 검색
        keywords = extract_keywords_fast(user_query)
        search_query = " ".join(keywords) if keywords else user_query
        sources = await run_in_threadpool(fetch_hybrid_news, search_query, display_count=5)
        
        sources_summary = "\n".join([
            f"[{i+1}] 제목: {s.get('title')}\n요약: {s.get('description')}\n출처 링크: {s.get('link')}"
            for i, s in enumerate(sources[:4])
        ])
        
        prompt = (
            "당신은 실시간 팩트체크 AI 어시스턴트입니다.\n"
            "사용자가 질문한 사실 관계나 소문/루머에 대해, 아래 실시간 검색된 최신 언론 보도 및 웹 자료를 바탕으로 진위 여부와 배경을 알기 쉽게 설명해 주세요.\n\n"
            f"사용자 질문: {user_query}\n\n"
            f"[실시간 수집된 관련 보도 자료]\n{sources_summary}\n\n"
            "답변 지침:\n"
            "1. 수집된 보도 내용을 바탕으로 사실(True), 허위(False), 논란/미확인 중 어떤 상태인지 명확히 짚어주세요.\n"
            "2. 친절하고 신뢰감 있는 어조로 2~3개 문단 이내로 요약해 설명하세요.\n"
            "3. 참고 자료가 부족하다면 섣불리 단정하지 말고 확인된 사실과 미확인 사실을 구분해 설명하세요."
        )
        
        answer = await run_in_threadpool(call_gemini_api, prompt)
        if not answer:
            answer = "실시간 검색 자료를 분석하지 못했습니다. 질문을 조금 더 구체적으로 작성해 보세요."
            
        formatted_sources = [
            {"title": s.get("title"), "link": s.get("link"), "description": s.get("description")}
            for s in sources[:4]
        ]
        
        return {
            "answer": answer,
            "sources": formatted_sources
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[-] 어시스턴트 챗봇 오류: {e}")
        raise HTTPException(status_code=500, detail="챗봇 분석 중 오류가 발생했습니다.")

if __name__ == "__main__":
    import uvicorn
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    print("[*] Fake News Defender 백엔드 서버를 가동합니다.")
    uvicorn.run("backend_app:app", host="127.0.0.1", port=8000, reload=True)
