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
    네이버 뉴스 검색 오픈 API를 통해 실시간 기사 리스트를 가져옵니다.
    
    :param client_id: 네이버 개발자 센터에서 발급받은 Client ID
    :param client_secret: 네이버 개발자 센터에서 발급받은 Client Secret
    :param query: 검색할 뉴스 키워드 (예: "A 장관 사퇴")
    :param display_count: 검색 결과 개수 (기본값 5개, 최대 100개)
    :return: 파싱된 뉴스 결과 리스트 (dict 형태)
    """
    # 검색어 인코딩
    enc_text = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/news.json?query={enc_text}&display={display_count}&sort=sim"
    
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [])
            
            parsed_results = []
            for item in items:
                # 네이버 API가 반환하는 타이틀/설명의 HTML 태그(<b>, &quot; 등) 제거
                title = item["title"].replace("<b>", "").replace("</b>", "").replace("&quot;", "\"")
                description = item["description"].replace("<b>", "").replace("</b>", "").replace("&quot;", "\"")
                
                parsed_results.append({
                    "title": title,
                    "link": item["originallink"] or item["link"], # 언론사 다이렉트 링크 우선
                    "description": description,
                    "pubDate": item["pubDate"]
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
    NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", "YOUR_CLIENT_ID")
    NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "YOUR_CLIENT_SECRET")
    
    if NAVER_CLIENT_ID == "YOUR_CLIENT_ID":
        print("💡 나중에 naver_news_api.py 파일 내부의 NAVER_CLIENT_ID와 SECRET을 실제 발급받으신 키로 변경하여 테스트해 보세요.")
    else:
        results = fetch_naver_news(NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, "인공지능 가짜뉴스")
        print(json.dumps(results, indent=4, ensure_ascii=False))
