import os
import sys
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

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

SUPABASE_ENABLED = bool(SUPABASE_URL and SUPABASE_KEY and SUPABASE_URL != "여기에_프로젝트_URL_입력")
if not SUPABASE_ENABLED:
    print("[-] 경고: Supabase URL 또는 API Key가 설정되지 않았습니다. 검사 결과가 저장되지 않으며 히스토리/통계는 빈 값으로 응답합니다.")

# Lazy loading helper for NLL model
_nll_model = None
_nll_threshold = None

def get_nll_model_lazy():
    global _nll_model, _nll_threshold
    if _nll_model is None:
        from fact_checker_by_url import load_nll_model
        _nll_model, _nll_threshold = load_nll_model()
    return _nll_model, _nll_threshold

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

@app.post("/api/check")
async def check_url(payload: CheckRequest):
    url = payload.url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="올바른 HTTP/HTTPS URL 형식을 입력해 주세요.")
        
    try:
        # Lazy load NLL model
        nll_model, nll_threshold = get_nll_model_lazy()
        
        # Run the hybrid detection pipeline
        result = check_url_validity(url, nll_model, nll_threshold)
        if not result:
            raise HTTPException(status_code=500, detail="기사 본문 크롤링에 실패했거나 올바르지 않은 페이지입니다.")
            
        # Store result in Supabase Database via REST API.
        # 저장 실패는 분석 결과 자체를 무효화하지 않도록 fail-soft로 처리합니다.
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

                resp = requests.post(f"{SUPABASE_URL}/rest/v1/checks", headers=headers, json=check_data)
                if resp.status_code != 201:
                    # Fallback: if 'claims_breakdown' column doesn't exist yet in checks table, retry without it
                    if 'claims_breakdown' in check_data:
                        print("[!] Warning: 'claims_breakdown' column might be missing. Retrying insert without it...")
                        del check_data['claims_breakdown']
                        resp = requests.post(f"{SUPABASE_URL}/rest/v1/checks", headers=headers, json=check_data)
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
                        "title": s['title'],
                        "link": s['link'],
                        "description": s['description'],
                        "pub_date": s['pubDate']
                    })

                if ref_data:
                    resp_ref = requests.post(f"{SUPABASE_URL}/rest/v1/check_references", headers=headers, json=ref_data)
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
        # Fetch checks joining with check_references as 'sources' sorting by created_at desc
        url = f"{SUPABASE_URL}/rest/v1/checks?select=*,sources:check_references(*)&order=created_at.desc"
        resp = requests.get(url, headers=headers)
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
        resp = requests.delete(url, headers=headers)
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
        # Query only the columns needed to calculate statistics (saves bandwidth)
        url = f"{SUPABASE_URL}/rest/v1/checks?select=verdict,nll_loss,contradiction_score"
        resp = requests.get(url, headers=headers)
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

# --- 추가 기능 API 엔드포인트 ---

class QueryRequest(BaseModel):
    query: str

class CommentRequest(BaseModel):
    author: str
    content: str
    user_token: Optional[str] = None

class ReactionRequest(BaseModel):
    emoji: str
    is_canceling: Optional[bool] = False

@app.get("/api/stats/rankings")
async def get_rankings():
    if not SUPABASE_ENABLED:
        return {"most_checked": [], "top_fakes": []}
    try:
        headers = get_supabase_headers()
        
        # 1. Fetch checks
        url = f"{SUPABASE_URL}/rest/v1/checks?select=url,title,verdict,contradiction_score,created_at"
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            raise Exception(f"Supabase checks 조회 실패 (HTTP {resp.status_code}): {resp.text}")
            
        rows = resp.json()
        
        # Calculate most checked URLs
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
            
        # Calculate top fakes
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

@app.post("/api/check/{check_id}/query")
async def query_check(check_id: int, payload: QueryRequest):
    user_query = payload.query.strip()
    if not user_query:
        raise HTTPException(status_code=400, detail="질문 내용을 입력해 주세요.")
        
    if not SUPABASE_ENABLED:
        raise HTTPException(status_code=503, detail="Supabase 설정이 되지 않아 기사 정보를 찾을 수 없습니다.")
        
    try:
        headers = get_supabase_headers()
        
        # 1. Fetch check info
        url = f"{SUPABASE_URL}/rest/v1/checks?id=eq.{check_id}"
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200 or not resp.json():
            raise HTTPException(status_code=404, detail="해당 검사 기사를 찾을 수 없습니다.")
        check_item = resp.json()[0]
        
        # 2. Run real-time hybrid search for the query
        from fact_checker_by_url import fetch_hybrid_news
        print(f"[*] 추가 분석 실시간 웹 검색 실행 중: {user_query}")
        sources = fetch_hybrid_news(user_query, display_count=5)
        
        sources_text = ""
        for i, s in enumerate(sources):
            sources_text += f"[참고 자료 {i+1}]\n제목: {s['title']}\n내용 요약: {s['description']}\n링크: {s['link']}\n\n"
            
        # 3. Build Gemini prompt
        from datetime import datetime
        current_date = datetime.now().strftime("%Y년 %m월 %d일")
        
        prompt = (
            f"현재 날짜: {current_date}\n"
            "당신은 가짜 뉴스를 전문적으로 판정하는 팩트체커 AI입니다.\n"
            "사용자가 검증 기사 본문에 대해 추가로 질문했습니다. 제공된 [검증 대상 기사]와 [추가 검색된 참고 자료]를 기반으로 사용자의 질문에 상세하고 객관적으로 답변해 주세요.\n\n"
            "[검증 대상 기사]\n"
            f"제목: {check_item['title']}\n"
            f"검증 내용 요약: {check_item['reason']}\n\n"
            "[사용자의 질문]\n"
            f"{user_query}\n\n"
            "[추가 검색된 참고 자료 목록]\n"
            f"{sources_text if sources_text else '검색된 관련 기사가 없습니다.'}\n"
            "답변 지침:\n"
            "1. 질문 내용이 사실(True)인지 거짓(False)인지 혹은 판단이 불가한지 명확히 답하고 근거를 서술해 주세요.\n"
            "2. 대조군 자료를 바탕으로 신뢰할 수 있게 설명하세요.\n"
            "3. 한글로 상세하지만 간결하게 3~4문장 정도로 답변을 완성하세요.\n"
            "4. 반드시 마크다운이나 JSON 기호 없이 일반 평서문 텍스트로만 답변해 주세요."
        )
        
        from fact_checker_by_url import GEMINI_API_KEY, call_gemini_api
        
        answer = "LLM 연동이 되어 있지 않아 추가 질문에 대한 분석을 진행할 수 없습니다."
        
        if GEMINI_API_KEY and GEMINI_API_KEY.strip() and GEMINI_API_KEY.strip() != "YOUR_GEMINI_API_KEY":
            try:
                output = call_gemini_api(prompt)
                if output:
                    answer = output
                else:
                    answer = "Gemini API 호출에 실패했습니다. 잠시 후 다시 시도해 주세요."
            except Exception as e:
                answer = f"Gemini API 호출 중 오류가 발생했습니다: {str(e)}"
        else:
            answer = "서버에 GEMINI_API_KEY 환경 변수가 설정되지 않아 실시간 AI 답변 기능을 제공할 수 없습니다."
            
        return {
            "query": user_query,
            "answer": answer,
            "sources": sources
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"추가 분석 실패: {str(e)}")

@app.post("/api/chat")
async def chat_general(payload: QueryRequest):
    user_query = payload.query.strip()
    if not user_query:
        raise HTTPException(status_code=400, detail="질문 내용을 입력해 주세요.")
        
    try:
        # Run real-time hybrid search for the general query
        from fact_checker_by_url import fetch_hybrid_news
        print(f"[*] AI 팩트체커 자유 질문 실시간 웹 검색 실행 중: {user_query}")
        sources = fetch_hybrid_news(user_query, display_count=5)
        
        sources_text = ""
        for i, s in enumerate(sources):
            sources_text += f"[참고 자료 {i+1}]\n제목: {s['title']}\n내용 요약: {s['description']}\n링크: {s['link']}\n\n"
            
        # Build Gemini prompt
        from datetime import datetime
        current_date = datetime.now().strftime("%Y년 %m월 %d일")
        
        prompt = (
            f"현재 날짜: {current_date}\n"
            "당신은 가짜 뉴스를 전문적으로 판정하는 팩트체커 AI 동반자입니다.\n"
            "사용자가 특정 기사 링크가 아닌, 자유롭게 팩트체크 질문을 던졌습니다. 제공된 [추가 검색된 참고 자료]를 기반으로 사용자의 질문에 매우 상세하고 친절하며 객관적으로 답변해 주세요.\n\n"
            "[사용자의 질문]\n"
            f"{user_query}\n\n"
            "[추가 검색된 참고 자료 목록]\n"
            f"{sources_text if sources_text else '검색된 관련 기사가 없습니다.'}\n"
            "답변 지침:\n"
            "1. 질문 내용이 언론 보도나 팩트 상 사실(True)인지 거짓(False)인지 혹은 판단유보(Suspicious)인지 두괄식으로 명확히 답해 주세요.\n"
            "2. 대조군 자료 및 교차 검증된 보도 내용을 바탕으로 논리정연하고 신뢰할 수 있게 설명하세요.\n"
            "3. 한글로 친절하되 객관적인 어조로 상세히 서술해 주세요.\n"
            "4. 마크다운 형식(글머리 기호, 굵은 글씨 등)을 활용해 가독성 있게 정리해 주세요."
        )
        
        from fact_checker_by_url import GEMINI_API_KEY, call_gemini_api
        
        answer = "LLM 연동이 되어 있지 않아 팩트체크 대화 분석을 진행할 수 없습니다."
        
        if GEMINI_API_KEY and GEMINI_API_KEY.strip() and GEMINI_API_KEY.strip() != "YOUR_GEMINI_API_KEY":
            try:
                output = call_gemini_api(prompt)
                if output:
                    answer = output
                else:
                    answer = "Gemini API 호출에 실패했습니다. 잠시 후 다시 시도해 주세요."
            except Exception as e:
                answer = f"Gemini API 호출 중 오류가 발생했습니다: {str(e)}"
        else:
            answer = "서버에 GEMINI_API_KEY 환경 변수가 설정되지 않아 실시간 AI 답변 기능을 제공할 수 없습니다."
            
        return {
            "query": user_query,
            "answer": answer,
            "sources": sources
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"AI 자유 질문 분석 실패: {str(e)}")

@app.get("/api/history/{check_id}/comments")
async def get_comments(check_id: int):
    if not SUPABASE_ENABLED:
        return []
    try:
        headers = get_supabase_headers()
        url = f"{SUPABASE_URL}/rest/v1/check_comments?check_id=eq.{check_id}&order=created_at.asc"
        resp = requests.get(url, headers=headers)
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
        resp = requests.post(f"{SUPABASE_URL}/rest/v1/check_comments", headers=headers, json=comment_data)
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
        
        # 1. Fetch the comment to verify ownership
        url = f"{SUPABASE_URL}/rest/v1/check_comments?id=eq.{comment_id}"
        resp_get = requests.get(url, headers=headers)
        if resp_get.status_code != 200 or not resp_get.json():
            raise HTTPException(status_code=404, detail="댓글을 찾을 수 없거나 이미 삭제되었습니다.")
            
        comment = resp_get.json()[0]
        db_token = comment.get("user_token")
        
        # Allow deletion if tokens match, or if db_token is empty (fallback for legacy comments)
        if db_token and db_token != user_token:
            raise HTTPException(status_code=403, detail="본인이 작성한 댓글만 삭제할 수 있습니다.")
            
        # 2. Delete from database
        del_url = f"{SUPABASE_URL}/rest/v1/check_comments?id=eq.{comment_id}"
        resp_del = requests.delete(del_url, headers=headers)
        if resp_del.status_code not in (200, 204):
            raise Exception(f"Supabase 댓글 삭제 실패 (HTTP {resp_del.status_code}): {resp_del.text}")
            
        return {"status": "success", "message": "댓글이 삭제되었습니다."}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"댓글 삭제 실패: {str(e)}")

@app.get("/api/history/{check_id}/reactions")
async def get_reactions(check_id: int):
    if not SUPABASE_ENABLED:
        return []
    try:
        headers = get_supabase_headers()
        url = f"{SUPABASE_URL}/rest/v1/check_reactions?check_id=eq.{check_id}"
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            raise Exception(f"Supabase 리액션 조회 실패 (HTTP {resp.status_code}): {resp.text}")
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"리액션 조회 실패: {str(e)}")

@app.post("/api/history/{check_id}/reactions")
async def add_reaction(check_id: int, payload: ReactionRequest):
    emoji = payload.emoji.strip()
    is_canceling = payload.is_canceling
    if not emoji:
        raise HTTPException(status_code=400, detail="이모지가 없습니다.")
        
    if not SUPABASE_ENABLED:
        raise HTTPException(status_code=503, detail="Supabase 설정이 필요합니다.")
        
    try:
        headers = get_supabase_headers()
        
        # 1. Fetch existing reaction
        url = f"{SUPABASE_URL}/rest/v1/check_reactions?check_id=eq.{check_id}&emoji=eq.{emoji}"
        resp_get = requests.get(url, headers=headers)
        
        if resp_get.status_code == 200 and resp_get.json():
            existing = resp_get.json()[0]
            if is_canceling:
                # Decrement count
                new_count = int(existing['count']) - 1
                if new_count <= 0:
                    # Delete the reaction row if count falls to 0
                    del_url = f"{SUPABASE_URL}/rest/v1/check_reactions?id=eq.{existing['id']}"
                    resp_del = requests.delete(del_url, headers=headers)
                    if resp_del.status_code not in (200, 204):
                        raise Exception(f"Supabase 리액션 삭제 실패 (HTTP {resp_del.status_code}): {resp_del.text}")
                    existing['count'] = 0
                    return existing
                else:
                    # Update count
                    update_url = f"{SUPABASE_URL}/rest/v1/check_reactions?id=eq.{existing['id']}"
                    resp_up = requests.patch(update_url, headers=headers, json={"count": new_count})
                    if resp_up.status_code not in (200, 204):
                        raise Exception(f"Supabase 리액션 수정 실패 (HTTP {resp_up.status_code}): {resp_up.text}")
                    existing['count'] = new_count
                    return existing
            else:
                # Increment count
                new_count = int(existing['count']) + 1
                update_url = f"{SUPABASE_URL}/rest/v1/check_reactions?id=eq.{existing['id']}"
                resp_up = requests.patch(update_url, headers=headers, json={"count": new_count})
                if resp_up.status_code not in (200, 204):
                    raise Exception(f"Supabase 리액션 수정 실패 (HTTP {resp_up.status_code}): {resp_up.text}")
                
                existing['count'] = new_count
                return existing
        else:
            if is_canceling:
                return {"check_id": check_id, "emoji": emoji, "count": 0}
                
            # Not exist -> insert
            reaction_data = {
                "check_id": check_id,
                "emoji": emoji,
                "count": 1
            }
            resp_in = requests.post(f"{SUPABASE_URL}/rest/v1/check_reactions", headers=headers, json=reaction_data)
            if resp_in.status_code != 201:
                raise Exception(f"Supabase 리액션 저장 실패 (HTTP {resp_in.status_code}): {resp_in.text}")
            return resp_in.json()[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"리액션 저장 실패: {str(e)}")

if __name__ == "__main__":
    # uvicorn은 로컬 개발 서버 실행에만 필요합니다 (서버리스 배포에는 불필요)
    import uvicorn
    # Prevent print encoding issues
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    print("[*] Supabase 클라우드 데이터베이스 모드로 Uvicorn 서버를 가동합니다.")
    uvicorn.run("backend_app:app", host="127.0.0.1", port=8000, reload=True)
