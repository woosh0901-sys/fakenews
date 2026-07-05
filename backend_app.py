import os
import sys
import requests
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# Import our NLL RAG pipeline and credentials
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from fact_checker_by_url import check_url_validity, get_trained_nll_model
from naver_news_api import SUPABASE_URL, SUPABASE_KEY

if not SUPABASE_URL or not SUPABASE_KEY or SUPABASE_URL == "여기에_프로젝트_URL_입력":
    print("[-] 경고: Supabase URL 또는 API Key가 설정되지 않았습니다. 환경 변수를 확인해 주세요.")

# Warm up NLL model
nll_model, nll_threshold = get_trained_nll_model()

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
        # Run the hybrid detection pipeline
        result = check_url_validity(url, nll_model, nll_threshold)
        if not result:
            raise HTTPException(status_code=500, detail="기사 본문 크롤링에 실패했거나 올바르지 않은 페이지입니다.")
            
        # Store result in Supabase Database via REST API
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
        
        resp = requests.post(f"{SUPABASE_URL}/rest/v1/checks", headers=headers, json=check_data)
        if resp.status_code != 201:
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
        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"탐지 분석 도중 에러가 발생했습니다: {str(e)}")

@app.get("/api/history")
async def get_history():
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

if __name__ == "__main__":
    # Prevent print encoding issues
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    print("[*] Supabase 클라우드 데이터베이스 모드로 Uvicorn 서버를 가동합니다.")
    uvicorn.run("backend_app:app", host="127.0.0.1", port=8000, reload=True)
