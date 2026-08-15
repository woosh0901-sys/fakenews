import os
import sys
import httpx
import urllib.parse
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

# Import our NLL RAG pipeline and credentials
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from fact_checker_by_url import check_url_validity
from naver_news_api import SUPABASE_URL, SUPABASE_KEY

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
    print("[-] 경고: Supabase URL 또는 API Key가 설정되지 않았습니다. 검사 결과가 저장되지 않으며 히스토리/통계는 빈 값으로 응답합니다.")

# NLL statistical filter model has been removed.


# FastAPI App
app = FastAPI(title="Fake News Defender Backend API", version="1.0.0")

# CORS setup for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/debug/env")
async def debug_env():
    """Temporary debug endpoint to verify environment variables are loaded."""
    from fact_checker_by_url import GEMINI_API_KEY as gkey
    return {
        "GEMINI_API_KEY": f"{gkey[:6]}...{gkey[-4:]}" if gkey and len(gkey) > 10 else f"EMPTY_OR_SHORT(len={len(gkey) if gkey else 0})",
        "NAVER_CLIENT_ID": bool(NAVER_CLIENT_ID if 'NAVER_CLIENT_ID' in dir() else os.environ.get("NAVER_CLIENT_ID")),
        "SUPABASE_URL": SUPABASE_URL[:30] + "..." if SUPABASE_URL and len(SUPABASE_URL) > 30 else str(SUPABASE_URL),
        "SUPABASE_ENABLED": SUPABASE_ENABLED,
        "IS_VERCEL": bool(os.environ.get("VERCEL")),
    }

@app.get("/api/debug/gemini")
async def debug_gemini():
    """Temporary debug endpoint to test actual Gemini API call."""
    import requests as req
    from fact_checker_by_url import GEMINI_API_KEY as gkey
    if not gkey:
        return {"error": "GEMINI_API_KEY is empty"}
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gkey.strip()}"
        payload = {"contents": [{"parts": [{"text": "Say hello in Korean, one sentence only."}]}]}
        resp = req.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
        return {
            "status_code": resp.status_code,
            "response_body": resp.json() if resp.status_code == 200 else resp.text[:500],
            "success": resp.status_code == 200
        }
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}

# Helper function to get Supabase API headers
def get_supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

class CheckRequest(BaseModel):
    url: str

class CommentRequest(BaseModel):
    author: str
    content: str
    user_token: Optional[str] = None


@app.post("/api/preview")
async def preview_article(payload: CheckRequest):
    """
    분석 로딩 화면용 경량 미리보기.
    LLM·DB를 거치지 않고 기사 제목/본문/출처만 빠르게 추출해 돌려준다.
    (본 분석 /api/check 와 병렬로 호출되어 '분석 중' 화면에 본문을 띄우는 용도)
    """
    url = payload.url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="올바른 HTTP/HTTPS URL 형식을 입력해 주세요.")

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
            raise HTTPException(status_code=422, detail="본문을 추출할 수 없는 페이지입니다.")

        return {
            "title": article.get("title", ""),
            "content": article.get("content", "")[:4000],
            "source": source,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"미리보기 추출 실패: {str(e)}")


@app.post("/api/check")
async def check_url(payload: CheckRequest):
    url = payload.url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="올바른 HTTP/HTTPS URL 형식을 입력해 주세요.")
        
    # 24시간 내 동일 URL에 대한 캐시가 있는지 먼저 확인하여 API 호출 횟수를 획기적으로 아낍니다.
    if SUPABASE_ENABLED:
        try:
            # Supabase timestamps are UTC, query using ISO UTC format
            time_limit = (datetime.utcnow() - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
            encoded_url = urllib.parse.quote(url)
            cache_query_url = f"{SUPABASE_URL}/rest/v1/checks?select=*,sources:check_references(*)&url=eq.{encoded_url}&created_at=gte.{time_limit}&order=created_at.desc&limit=1"
            headers = get_supabase_headers()
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                cache_resp = await client.get(cache_query_url, headers=headers)
                if cache_resp.status_code == 200:
                    cache_data = cache_resp.json()
                    if cache_data and len(cache_data) > 0:
                        cache_item = cache_data[0]
                        if cache_item.get("verdict") == "REAL":
                            print(f"[★] 동일 URL에 대한 최근 24시간 내 '진실(REAL)' 캐시된 검사 결과가 있어 DB에서 즉시 반환합니다: {url}")
                            
                            # Reference format normalization
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
            print(f"[-] 캐시 조회 실패 (정상 팩트체크 파이프라인으로 진행): {cache_err}")
            
    try:
        # Run the fact-checking pipeline in a separate thread pool to prevent event loop blocking
        result = await run_in_threadpool(check_url_validity, url)
        if not result:
            raise HTTPException(status_code=500, detail="기사 본문 크롤링에 실패했거나 올바르지 않은 페이지입니다.")
            
        # Store result in Supabase Database via REST API asynchronously.
        result['id'] = None
        if SUPABASE_ENABLED:
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
                                raise Exception(f"Supabase checks 저장 실패 (HTTP {resp.status_code}): {resp.text}")
                        else:
                            raise Exception(f"Supabase checks 저장 실패 (HTTP {resp.status_code}): {resp.text}")

                    inserted_check = resp.json()[0]
                    check_id = inserted_check['id']

                    # Insert references if present (Stage 2)
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
                            raise Exception(f"Supabase check_references 저장 실패 (HTTP {resp_ref.status_code}): {resp_ref.text}")

                    result['id'] = check_id
            except Exception as db_err:
                print(f"[-] 검사 결과 저장 실패 (분석 결과는 정상 반환): {db_err}")
                result['warning'] = f"검사는 완료되었지만 결과를 데이터베이스에 저장하지 못했습니다. (오류: {str(db_err)})"
        else:
            result['warning'] = "서버에 Supabase 환경 변수가 설정되지 않아 검사 결과가 저장되지 않았습니다."

        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"탐지 분석 도중 에러가 발생했습니다: {str(e)}")

@app.get("/api/history")
async def get_history():
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
                raise Exception(f"Supabase history 조회 실패 (HTTP {resp.status_code}): {resp.text}")
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"히스토리 조회 실패: {str(e)}")

@app.delete("/api/history/{check_id}")
async def delete_history_item(check_id: int):
    if not SUPABASE_ENABLED:
        raise HTTPException(status_code=503, detail="서버에 Supabase 환경 변수가 설정되지 않아 히스토리 기능을 사용할 수 없습니다.")
    try:
        headers = get_supabase_headers()
        url = f"{SUPABASE_URL}/rest/v1/checks?id=eq.{check_id}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.delete(url, headers=headers)
            if resp.status_code not in (200, 204):
                raise Exception(f"Supabase 삭제 실패 (HTTP {resp.status_code}): {resp.text}")
            return {"status": "success", "message": "성공적으로 삭제되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"삭제 실패: {str(e)}")

@app.get("/api/stats")
async def get_stats():
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
                raise Exception(f"Supabase stats 조회 실패 (HTTP {resp.status_code}): {resp.text}")
            
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
                    total_nll += float(nll)
                    nll_count += 1
                    
                total_score += float(row.get("contradiction_score") or 0.0)
                
            return {
                "total_checks": total_checks,
                "real_count": real_count,
                "fake_count": fake_count,
                "suspicious_count": suspicious_count,
                "avg_nll": round(total_nll / nll_count, 4) if nll_count > 0 else 0.0,
                "avg_contradiction_score": round(total_score / total_checks, 4)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"통계 계산 실패: {str(e)}")

@app.get("/api/stats/rankings")
async def get_rankings():
    if not SUPABASE_ENABLED:
        return {"most_checked": [], "top_fakes": []}
    try:
        headers = get_supabase_headers()
        url = f"{SUPABASE_URL}/rest/v1/checks?select=url,title,verdict,contradiction_score,created_at"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                raise Exception(f"Supabase checks 조회 실패 (HTTP {resp.status_code}): {resp.text}")
            rows = resp.json()
        
        from collections import Counter
        url_counts = Counter()
        url_titles = {}
        for r in rows:
            url_counts[r['url']] += 1
            r_created = r.get('created_at') or ''
            if r['url'] not in url_titles or r_created > url_titles[r['url']]['created_at']:
                url_titles[r['url']] = {'title': r['title'], 'created_at': r_created}
                
        most_checked = []
        for u, count in url_counts.most_common(5):
            most_checked.append({
                "url": u,
                "title": url_titles[u]['title'],
                "count": count
            })
            
        fakes = [r for r in rows if r['verdict'] in ('FAKE', 'SUSPICIOUS')]
        fakes.sort(key=lambda x: x['contradiction_score'], reverse=True)
        
        top_fakes = []
        seen_urls = set()
        for f in fakes:
            if f['url'] not in seen_urls:
                seen_urls.add(f['url'])
                top_fakes.append({
                    "url": f['url'],
                    "title": f['title'],
                    "contradiction_score": f['contradiction_score'],
                    "verdict": f['verdict']
                })
                if len(top_fakes) >= 5:
                    break
                    
        return {
            "most_checked": most_checked,
            "top_fakes": top_fakes
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"랭킹 조회 실패: {str(e)}")

@app.get("/api/history/{check_id}/comments")
async def get_comments(check_id: int):
    if not SUPABASE_ENABLED:
        return []
    try:
        headers = get_supabase_headers()
        url = f"{SUPABASE_URL}/rest/v1/check_comments?check_id=eq.{check_id}&order=created_at.asc"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                raise Exception(f"Supabase 댓글 조회 실패 (HTTP {resp.status_code}): {resp.text}")
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"댓글 조회 실패: {str(e)}")

@app.post("/api/history/{check_id}/comments")
async def add_comment(check_id: int, payload: CommentRequest):
    author = payload.author.strip() or "익명"
    content = payload.content.strip()
    user_token = payload.user_token
    if not content:
        raise HTTPException(status_code=400, detail="댓글 내용을 입력해 주세요.")
        
    if not SUPABASE_ENABLED:
        raise HTTPException(status_code=503, detail="Supabase 설정이 필요합니다.")
        
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
                raise Exception(f"Supabase 댓글 저장 실패 (HTTP {resp.status_code}): {resp.text}")
            return resp.json()[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"댓글 저장 실패: {str(e)}")

@app.delete("/api/history/{check_id}/comments/{comment_id}")
async def delete_comment(check_id: int, comment_id: int, user_token: str):
    if not SUPABASE_ENABLED:
        raise HTTPException(status_code=503, detail="Supabase 설정이 필요합니다.")
        
    try:
        headers = get_supabase_headers()
        url = f"{SUPABASE_URL}/rest/v1/check_comments?id=eq.{comment_id}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp_get = await client.get(url, headers=headers)
            if resp_get.status_code != 200 or not resp_get.json():
                raise HTTPException(status_code=404, detail="댓글을 찾을 수 없거나 이미 삭제되었습니다.")
                
            comment = resp_get.json()[0]
            db_token = comment.get("user_token")
            
            if db_token and db_token != user_token:
                raise HTTPException(status_code=403, detail="본인이 작성한 댓글만 삭제할 수 있습니다.")
                
            del_url = f"{SUPABASE_URL}/rest/v1/check_comments?id=eq.{comment_id}"
            resp_del = await client.delete(del_url, headers=headers)
            if resp_del.status_code not in (200, 204):
                raise Exception(f"Supabase 댓글 삭제 실패 (HTTP {resp_del.status_code}): {resp_del.text}")
                
            return {"status": "success", "message": "댓글이 삭제되었습니다."}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"댓글 삭제 실패: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    print("[*] Supabase 클라우드 데이터베이스 모드로 Uvicorn 서버를 가동합니다.")
    uvicorn.run("backend_app:app", host="127.0.0.1", port=8000, reload=True)
