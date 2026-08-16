import os
import requests
import urllib.parse
import json
from dotenv import load_dotenv

# Load credentials from .env file
base_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(base_dir, ".env"))

# Naver News Search API Credentials
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")

# Gemini API Key (무료 발급: https://aistudio.google.com/ )
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Supabase 클라우드 데이터베이스 설정 (https://supabase.com )
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def fetch_naver_news(client_id, client_secret, query, display_count=5):
    """
    NAVER Cloud Platform NAVER API HUB 뉴스 검색 API를 통해 실시간 기사 리스트를 가져옵니다.
    
    :param client_id: NAVER Cloud Platform NAVER API HUB에서 발급받은 Client ID
    :param client_secret: NAVER Cloud Platform NAVER API HUB에서 발급받은 Client Secret
    :param query: 검색할 뉴스 키워드 (예: "A 장관 사퇴")
    :param display_count: 검색 결과 개수 (기본값 5개, 최대 100개)
    :return: 파싱된 뉴스 결과 리스트 (dict 형태)
    """
    # 검색어 인코딩
    enc_text = urllib.parse.quote(query)
    url = f"https://naverapihub.apigw.ntruss.com/search/v1/news?query={enc_text}&display={display_count}&sort=sim"
    
    headers = {
        "X-NCP-APIGW-API-KEY-ID": client_id,
        "X-NCP-APIGW-API-KEY": client_secret
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=3.0)
        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [])
            
            parsed_results = []
            for item in items:
                # 네이버 API가 반환하는 타이틀/설명의 HTML 태그(<b>, &quot; 등) 제거
                raw_title = item.get("title", "")
                raw_desc = item.get("description", "")
                title = raw_title.replace("<b>", "").replace("</b>", "").replace("&quot;", "\"")
                description = raw_desc.replace("<b>", "").replace("</b>", "").replace("&quot;", "\"")
                link = item.get("originallink") or item.get("link", "")
                pub_date = item.get("pubDate", "")
                
                parsed_results.append({
                    "title": title,
                    "link": link, # 언론사 다이렉트 링크 우선
                    "description": description,
                    "pubDate": pub_date
                })
            return parsed_results
        else:
            print(f"[Error] Naver News API request failed with status code: {response.status_code}")
            return []
    except Exception as e:
        print(f"[Error] Connection to Naver News API failed: {e}")
        return []

# 테스트 코드 (실행 확인용)
if __name__ == "__main__":
    # Use environment variables instead of hardcoding credentials for security
    client_id = os.environ.get("NAVER_CLIENT_ID", "")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET", "")
    
    if not client_id or not client_secret or client_id == "YOUR_CLIENT_ID":
        print("💡 NAVER API HUB에서 발급받은 Client ID와 Client Secret을 NAVER_CLIENT_ID, NAVER_CLIENT_SECRET 환경변수에 설정하여 테스트해 보세요.")
    else:
        results = fetch_naver_news(client_id, client_secret, "인공지능 가짜뉴스")
        print(json.dumps(results, indent=4, ensure_ascii=False))
