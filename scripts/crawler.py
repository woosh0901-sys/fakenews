import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup
import urllib.parse

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# Pre-urlencoded queries to prevent Windows CP949 encoding errors
# "정치" -> %EC%A0%95%EC%B9%98
# "사회" -> %EC%82%AC%ED%9A%8C
# "경제" -> %EA%B2%BD%EC%A0%9C
REAL_QUERIES = ["%EC%A0%95%EC%B9%98", "%EC%82%AC%ED%9A%8C", "%EA%B2%BD%EC%A0%9C"]

# "팩트체크 사실아님" -> %ED%8C%A9%ED%8A%B8%EC%B2%B4%ED%81%AC%20%EC%82%AC%EC%8B%A4%EC%95%84%EB%8B%98
# "팩트체크 거짓" -> %ED%8C%A9%ED%8A%B8%EC%B2%B4%ED%81%AC%20%EA%B1%B0%EC%A7%93
# "팩트체크 왜곡" -> %ED%8C%A9%ED%8A%B8%EC%B2%B4%ED%81%AC%20%EC%99%9C%EA%B3%A1
# "팩트체크 허위" -> %ED%8C%A9%ED%8A%B8%EC%B2%B4%ED%81%AC%20%ED%97%88%EC%9C%84
FAKE_QUERIES = [
    "%ED%8C%A9%ED%8A%B8%EC%B2%B4%ED%81%AC%20%EC%82%AC%EC%8B%A4%EC%95%84%EB%8B%98",
    "%ED%8C%A9%ED%8A%B8%EC%B2%B4%ED%81%AC%20%EA%B1%B0%EC%A7%93",
    "%ED%8C%A9%ED%8A%B8%EC%B2%B4%ED%81%AC%20%EC%99%9C%EA%B3%A1",
    "%ED%8C%A9%ED%8A%B8%EC%B2%B4%ED%81%AC%20%ED%97%88%EC%9C%84"
]

def get_naver_news_links_multi(queries, target_count=100):
    links = set()
    
    for query_encoded in queries:
        if len(links) >= target_count:
            break
            
        print(f"Searching Naver News links for encoded query: '{query_encoded}'... Currently gathered: {len(links)}")
        start = 1
        consecutive_failures = 0
        
        while len(links) < target_count:
            url = f"https://search.naver.com/search.naver?where=news&query={query_encoded}&start={start}"
            try:
                resp = requests.get(url, headers=HEADERS, timeout=10)
                if resp.status_code != 200:
                    print(f"Failed to fetch search page, status: {resp.status_code}")
                    break
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                found_any = False
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if "n.news.naver.com/mnews/article" in href:
                        # Normalize url by stripping tracking params
                        normalized = href.split('?')[0]
                        if normalized not in links:
                            links.add(normalized)
                            found_any = True
                            if len(links) >= target_count:
                                break
                
                if not found_any:
                    consecutive_failures += 1
                    if consecutive_failures > 3:
                        print("No more new Naver News links found for this query.")
                        break
                else:
                    consecutive_failures = 0
                    
                start += 10
                time.sleep(0.3)
            except Exception as e:
                print(f"Error during search paging: {e}")
                break
                
    return list(links)[:target_count]

def scrape_article_content(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return None
            
        # explicitly set encoding to prevent Korean letters from breaking
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Naver News main text container
        article_body = soup.find('article', id='dic_area')
        if not article_body:
            article_body = soup.find('div', id='articleBodyContents')
            
        if not article_body:
            return None
            
        # Clean text
        text = article_body.get_text(separator=' ').strip()
        text = re.sub(r'\s+', ' ', text)
        
        # Get Title
        title_el = soup.find('h2', id='title_area')
        if not title_el:
            title_el = soup.find('h3', id='articleTitle')
        title = title_el.get_text().strip() if title_el else "No Title"
        
        return {
            'url': url,
            'title': title,
            'content': text
        }
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

def main():
    target_count = 1000
    
    # 1. Scrape Real News
    real_links = get_naver_news_links_multi(REAL_QUERIES, target_count)
    real_articles = []
    print(f"Scraping {len(real_links)} real news articles...")
    for idx, url in enumerate(real_links):
        print(f"[{idx+1}/{len(real_links)}] Scraping {url}")
        art = scrape_article_content(url)
        if art:
            real_articles.append(art)
        time.sleep(0.2)
        
    with open("real_news.json", "w", encoding="utf-8") as f:
        json.dump(real_articles, f, ensure_ascii=False, indent=4)
    print(f"Saved {len(real_articles)} real news articles to real_news.json")
    
    # 2. Scrape Fake News (Fact-checked claims)
    fake_links = get_naver_news_links_multi(FAKE_QUERIES, target_count)
    fake_articles = []
    print(f"Scraping {len(fake_links)} fake news articles...")
    for idx, url in enumerate(fake_links):
        print(f"[{idx+1}/{len(fake_links)}] Scraping {url}")
        art = scrape_article_content(url)
        if art:
            fake_articles.append(art)
        time.sleep(0.2)
        
    with open("fake_news.json", "w", encoding="utf-8") as f:
        json.dump(fake_articles, f, ensure_ascii=False, indent=4)
    print(f"Saved {len(fake_articles)} fake news articles to fake_news.json")

if __name__ == "__main__":
    # Prevent stdout encoding errors on Windows terminal
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    main()
