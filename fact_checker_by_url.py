import sys
import os
import requests
import json
import re
import math
from bs4 import BeautifulSoup

# Import Naver News API module from local folder robustly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from naver_news_api import fetch_naver_news

# Import Trigram Language Model from reconstruction_detector
from reconstruction_detector import TrigramLanguageModel, custom_tokenize

OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen3.5:latest"

# Vercel 등 서버리스 환경에서는 localhost Ollama에 접근할 수 없으므로 폴백을 건너뜁니다.
IS_SERVERLESS = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

# Real credentials (loaded automatically from naver_news_api.py if set, or defined here)
from naver_news_api import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, GEMINI_API_KEY

def fetch_duckduckgo_search(query, max_results=3):
    """
    네이버 뉴스 검색 API에 걸리지 않는 IT/글로벌/구글 뉴스 기사를 커버하기 위해
    DuckDuckGo 실시간 웹 검색(HTML 모드)을 수행합니다. (무료, API 키 불필요)
    """
    import urllib.parse
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    data = {
        "q": query
    }
    results = []
    
    # Filter list for low-credibility copy-paste sources and forums to prevent rumor dilution
    EXCLUDED_DOMAINS = [
        "instagram.com", "facebook.com", "twitter.com", "x.com", "tiktok.com", 
        "youtube.com", "dcinside.com", "fmkorea.com", "ruliweb.com", "clien.net", 
        "ppomppu.co.kr", "instiz.net", "inven.co.kr", "todayhumor.co.kr", 
        "mlbpark.donga.com", "slrclub.com"
    ]
    
    try:
        resp = requests.post(url, headers=headers, data=data, timeout=3)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            # DuckDuckGo HTML 검색 결과 파싱
            for item in soup.find_all('div', class_='result__body')[:max_results + 10]: # Fetch extra to allow filtering
                if len(results) >= max_results:
                    break
                title_elem = item.find('a', class_='result__url')
                snippet_elem = item.find('a', class_='result__snippet')
                if title_elem and snippet_elem:
                    title = title_elem.get_text().strip()
                    link = title_elem['href']
                    description = snippet_elem.get_text().strip()
                    
                    # DuckDuckGo 리다이렉트 URL 추출 및 디코딩
                    if "uddg=" in link:
                        try:
                            link = urllib.parse.unquote(link.split("uddg=")[1].split("&")[0])
                        except:
                            pass
                            
                    # Exclude low-credibility rumor mills and SNS
                    is_excluded = False
                    for domain in EXCLUDED_DOMAINS:
                        if domain in link:
                            is_excluded = True
                            break
                    if is_excluded:
                        continue
                        
                    results.append({
                        "title": title,
                        "link": link,
                        "description": description,
                        "pubDate": "실시간 웹 검색"
                    })
    except Exception as e:
        print(f"[-] DuckDuckGo 웹 검색 중 에러 발생: {e}")
    return results

def translate_ko_to_en(text):
    """
    구글 번역 무료 웹 API를 이용해 한글 쿼리를 영어로 번역합니다.
    """
    import urllib.parse
    try:
        encoded_text = urllib.parse.quote(text)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=ko&tl=en&dt=t&q={encoded_text}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            translated = data[0][0][0]
            return translated
    except Exception as e:
        print(f"    [-] 검색 쿼리 영문 번역 실패 (로컬 검색어 유지): {e}")
    return text

def fetch_hybrid_news(query, display_count=3):
    """
    네이버 뉴스 검색 API와 DuckDuckGo 실시간 웹 검색 결과를 모두 수집하고 병합하여
    네이버와 구글 검색을 완벽히 모방하는 하이브리드 대조 결과를 만듭니다.
    """
    # 1. 네이버 뉴스 검색 시도
    naver_sources = fetch_naver_news(NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, query, display_count=display_count)
    print(f"    - 네이버 뉴스 검색 결과: {len(naver_sources)}개 수집됨.")
    
    # 2. DuckDuckGo 실시간 웹 검색 실행 (1회만 호출하여 속도 최적화)
    web_sources = fetch_duckduckgo_search(query, max_results=display_count)
    print(f"    - DuckDuckGo 웹 검색 결과: {len(web_sources)}개 수집됨.")
        
    # 3. 중복 제거하며 병합 (네이버 결과 우선순위)
    merged = []
    existing_links = set()
    
    for s in naver_sources:
        if s['link'] not in existing_links:
            merged.append(s)
            existing_links.add(s['link'])
            
    for s in web_sources:
        if s['link'] not in existing_links:
            merged.append(s)
            existing_links.add(s['link'])
            
    print(f"    - 하이브리드 검색 병합 완료: 통합 {len(merged)}개 소스 확보.")
    return merged[:display_count]

def scrape_url_content(url, timeout=5):
    """
    주어진 URL 웹페이지를 크롤링하여 기사 제목과 본문을 추출합니다.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code != 200:
            print(f"[-] 웹페이지 접속 실패 (HTTP {resp.status_code}): {url}")
            return None
            
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 1. 제목(Title) 추출
        title = ""
        # OpenGraph 타이틀 우선 확인
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title = og_title['content'].strip()
            
        if not title:
            # Naver News 전용 타이틀 태그
            title_el = soup.find('h2', id='title_area') or soup.find('h3', id='articleTitle')
            # 일반 웹 h1 혹은 title
            if not title_el:
                title_el = soup.find('h1') or soup.find('title')
            title = title_el.get_text().strip() if title_el else "No Title"
            
        # 2. 본문(Content) 추출
        # 불필요한 태그 제거 (스크립트, 스타일, 네비게이션, 푸터 등)
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"]):
            element.decompose()
            
        # Remove elements commonly representing popular articles, sidebars, related posts, ads, tags etc.
        noise_keywords = [
            "popular", "ranking", "recommend", "relation", "related", "sidebar", "comment", "reply", 
            "social", "share", "ad-", "banner", "tag", "widget", "aside", "navigation",
            "side_list", "hot_news", "popular_news", "side_area", "right_area",
            "popular-news", "related-news", "most-read", "trending", "w_side_list"
        ]
        
        # Collect noise elements first, then decompose to avoid modifying tree during iteration
        to_decompose = []
        for element in soup.find_all(True):
            if element.parent is None:
                continue
            if element.get('class'):
                cls_list = element.get('class')
                cls_str = " ".join(cls_list).lower() if isinstance(cls_list, list) else str(cls_list).lower()
                if any(k in cls_str for k in noise_keywords):
                    to_decompose.append(element)
                    continue
            if element.get('id'):
                el_id = str(element.get('id')).lower()
                if any(k in el_id for k in noise_keywords):
                    to_decompose.append(element)
                    continue
                    
        for el in to_decompose:
            try:
                el.decompose()
            except Exception:
                pass
            
        text = ""
        # Naver News인 경우 특정 본문 영역 추출
        if "news.naver.com" in url:
            article_body = soup.find('article', id='dic_area') or soup.find('div', id='articleBodyContents') or soup.find('div', id='articleBody')
            if article_body:
                text = article_body.get_text(separator=' ').strip()
        elif "news.sbs.co.kr" in url:
            article_body = soup.find('div', class_='main_text') or soup.find('div', itemprop='articleBody')
            if article_body:
                text = article_body.get_text(separator=' ').strip()
        elif "v.daum.net" in url or "news.v.daum.net" in url:
            article_body = soup.find('div', class_='article_view') or soup.find('section', class_='box_article')
            if article_body:
                text = article_body.get_text(separator=' ').strip()
        elif "news.nate.com" in url:
            article_body = soup.find('div', id='realArtcBody') or soup.find('div', id='artcBody')
            if article_body:
                text = article_body.get_text(separator=' ').strip()
                
        if not text:
            # 일반 사이트: 문단(<p>) 태그에서 텍스트 수집
            paragraphs = soup.find_all('p')
            if paragraphs:
                text = " ".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 15])
            
            # 그것도 없으면 전체 바디 텍스트
            if not text:
                text = soup.body.get_text(separator=' ').strip() if soup.body else soup.get_text(separator=' ').strip()
                
        # 연속된 공백 및 줄바꿈 정리
        text = re.sub(r'\s+', ' ', text).strip()
        title = re.sub(r'\s+', ' ', title).strip()
        
        # 3. 커뮤니티 게시물 또는 본문이 짧고 외부 뉴스 링크가 포함되어 있는 경우 원본 뉴스 기사를 크롤링하여 본문에 병합
        is_community = any(dom in url for dom in [
            "dcinside.com", "fmkorea.com", "ruliweb.com", "clien.net", "ppomppu.co.kr", 
            "instiz.net", "inven.co.kr", "todayhumor.co.kr", "mlbpark.donga.com", 
            "slrclub.com", "pann.nate.com", "bobaedream.co.kr", "theqoo.net", "instiz"
        ])
        
        found_links = []
        if is_community or (text and len(text) < 150):
            news_patterns = [
                r'news\.naver\.com', r'v\.daum\.net', r'news\.v\.daum\.net',
                r'chosun\.com', r'donga\.com', r'joongang\.co\.kr', r'hani\.co\.kr',
                r'khan\.co\.kr', r'yna\.co\.kr', r'hankyung\.com', r'mk\.co\.kr',
                r'sedaily\.com', r'mt\.co\.kr', r'moneytoday', r'seoul\.co\.kr',
                r'segye\.com', r'kmib\.co\.kr', r'munhwa\.com', r'kukinews',
                r'nocutnews', r'ytn\.co\.kr', r'sbs\.co\.kr', r'kbs\.co\.kr',
                r'imbc\.com', r'newsis\.com', r'news1\.kr', r'heraldcorp\.com',
                r'asiae\.co\.kr', r'etnews\.com', r'digitaltimes'
            ]
            
            for a in soup.find_all('a', href=True):
                href = a['href']
                for pat in news_patterns:
                    if re.search(pat, href) and href not in found_links:
                        found_links.append(href)
                        break
                        
            # 본문 텍스트 내에 포함된 raw URL 탐색
            raw_urls = re.findall(r'https?://[^\s<>"]+', text)
            for r_url in raw_urls:
                for pat in news_patterns:
                    if re.search(pat, r_url) and r_url not in found_links:
                        found_links.append(r_url)
                        break
                        
        if found_links:
            print(f"    [+] 본문 내 뉴스 원본 링크 감지: {found_links}")
            crawled_contents = []
            links_to_crawl = [link for link in found_links[:3] if link != url]
            if links_to_crawl:
                from concurrent.futures import ThreadPoolExecutor
                def crawl_link(l):
                    try:
                        return scrape_url_content(l, timeout=3)
                    except Exception:
                        return None
                
                with ThreadPoolExecutor(max_workers=3) as executor:
                    crawled_results = list(executor.map(crawl_link, links_to_crawl))
                
                for original_article in crawled_results:
                    if original_article and original_article.get('content'):
                        crawled_contents.append(f"[연동 뉴스 원본: {original_article['title']}]\n{original_article['content']}")
            
            if crawled_contents:
                merged_text = "\n\n".join(crawled_contents)
                text = f"{text} \n\n[연동 뉴스 원본 본문 목록]\n{merged_text}"
                
        return {
            'url': url,
            'title': title,
            'content': text
        }
    except Exception as e:
        print(f"[-] 웹 크롤링 중 에러 발생: {e}")
        return None

# 인스타그램 게시물/릴스 URL 패턴
INSTAGRAM_URL_RE = re.compile(r'instagram\.com/(?:[A-Za-z0-9_.]+/)?(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)')

def is_instagram_url(url):
    return bool(INSTAGRAM_URL_RE.search(url))

def scrape_instagram_post(url):
    """
    인스타그램 공개 게시물의 캡션을 추출합니다.
    일반 브라우저 UA로는 로그인 벽에 막히지만, 링크 미리보기용 크롤러 UA(facebookexternalhit)로
    요청하면 공개 게시물의 og:title / og:description 메타 태그에 캡션 전문이 담겨 옵니다.
    """
    m = INSTAGRAM_URL_RE.search(url)
    if not m:
        return None
    shortcode = m.group(1)
    canonical_url = f"https://www.instagram.com/p/{shortcode}/"

    headers = {
        "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"
    }
    try:
        resp = requests.get(canonical_url, headers=headers, timeout=5)
        if resp.status_code != 200:
            print(f"[-] 인스타그램 게시물 접근 실패 (HTTP {resp.status_code}): {canonical_url}")
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')
        og_title = soup.find('meta', property='og:title')
        og_desc = soup.find('meta', property='og:description') or soup.find('meta', attrs={'name': 'description'})

        og_title_text = og_title['content'].strip() if og_title and og_title.get('content') else ""
        og_desc_text = og_desc['content'].strip() if og_desc and og_desc.get('content') else ""

        # Robust caption extraction (supports multilingual formats including English, Korean, etc.)
        caption = ""
        author = ""
        username = ""
        post_date = ""
        
        # 1. Try English og:title format
        title_match = re.match(r'^(.*?) on Instagram:\s*[\"“](.*)[\"”]\s*$', og_title_text, re.DOTALL)
        if title_match:
            author = title_match.group(1).strip()
            caption = title_match.group(2).strip()
            
        # 2. Try Korean og:title format: 'Instagram의 {표시 이름}: "{캡션 전문}"'
        if not caption:
            ko_title_match = re.match(r'^Instagram의\s+(.*?):\s*[\"“](.*)[\"”]\s*$', og_title_text, re.DOTALL)
            if ko_title_match:
                author = ko_title_match.group(1).strip()
                caption = ko_title_match.group(2).strip()

        # 3. Try English og:description format
        desc_match = re.match(r'^.*? - ([A-Za-z0-9_.]+) on ([^:]+):\s*[\"“](.*)[\"”]\s*$', og_desc_text, re.DOTALL)
        if desc_match:
            username = desc_match.group(1)
            post_date = desc_match.group(2).strip()
            if not caption:
                caption = desc_match.group(3).strip()
                
        # 4. Try Korean og:description format: '좋아요 {N}개, 댓글 {M}개 - Instagram의 {유저명}님: "{캡션}"'
        if not caption:
            ko_desc_match = re.search(r'Instagram의\s+([A-Za-z0-9_.]+)님:\s*[\"“](.*)[\"”]\s*$', og_desc_text, re.DOTALL)
            if ko_desc_match:
                username = ko_desc_match.group(1)
                caption = ko_desc_match.group(2).strip()

        # 5. Universal Fallback: Just extract the first double-quoted/curly-quoted text block
        if not caption:
            quote_match = re.search(r'[\"“](.*)[\"”]', og_title_text, re.DOTALL)
            if quote_match:
                caption = quote_match.group(1).strip()
                author = og_title_text.split("on Instagram")[0].split("Instagram의")[-1].split(":")[0].strip()
                
        if not caption:
            quote_match = re.search(r'[\"“](.*)[\"”]', og_desc_text, re.DOTALL)
            if quote_match:
                caption = quote_match.group(1).strip()

        if not caption:
            print("[-] 인스타그램 캡션을 추출하지 못했습니다. 비공개 계정이거나 캡션이 없는 게시물일 수 있습니다.")
            return None

        caption = re.sub(r'\s+', ' ', caption).strip()

        # 검색 키워드 추출에 쓰일 제목: 캡션 첫 문장(최대 60자)
        first_line = caption.split(". ")[0][:60].strip()
        display_author = username or author
        title = f"[인스타그램] {display_author}: {first_line}" if display_author else f"[인스타그램] {first_line}"

        content = caption
        if post_date:
            content = f"(게시일: {post_date}) {content}"

        print(f"    - 인스타그램 게시물 감지 (작성자: {display_author or '알 수 없음'})")
        return {
            'url': canonical_url,
            'title': title,
            'content': content,
            'search_text': first_line  # 검색어 추출은 대괄호 접두어 없이 캡션만 사용
        }
    except Exception as e:
        print(f"[-] 인스타그램 게시물 크롤링 중 에러 발생: {e}")
        return None

# 트위터(X) 게시물 URL 패턴 (twitter.com / x.com / mobile.twitter.com)
TWITTER_URL_RE = re.compile(r'\b(?:twitter|x)\.com/([A-Za-z0-9_]+)/status(?:es)?/(\d+)')

def is_twitter_url(url):
    return bool(TWITTER_URL_RE.search(url))

def scrape_twitter_post(url):
    """
    트위터(X) 공개 게시물의 본문을 추출합니다.
    x.com은 로그인 없이는 페이지 크롤링이 막혀 있지만, 공개 oEmbed API
    (publish.twitter.com/oembed)는 API 키 없이 트윗 본문 HTML을 반환합니다.
    """
    m = TWITTER_URL_RE.search(url)
    if not m:
        return None
    username, tweet_id = m.group(1), m.group(2)
    canonical_url = f"https://twitter.com/{username}/status/{tweet_id}"

    try:
        resp = requests.get(
            "https://publish.twitter.com/oembed",
            params={"url": canonical_url, "omit_script": "true", "lang": "ko"},
            timeout=5
        )
        if resp.status_code != 200:
            print(f"[-] 트위터 oEmbed 조회 실패 (HTTP {resp.status_code}). 삭제되었거나 비공개 계정의 게시물일 수 있습니다.")
            return None

        data = resp.json()
        html = data.get("html", "")
        soup = BeautifulSoup(html, "html.parser")
        p = soup.find("p")
        text = p.get_text(" ", strip=True) if p else soup.get_text(" ", strip=True)

        # 첨부 이미지/단축 링크 텍스트(pic.twitter.com, t.co)는 본문이 아니므로 제거
        text = re.sub(r'(?:pic\.twitter\.com|https?://t\.co)/\S+', '', text)
        text = re.sub(r'\s+', ' ', text).strip()

        if not text:
            print("[-] 트윗 본문을 추출하지 못했습니다. 이미지/영상만 있는 게시물일 수 있습니다.")
            return None

        author = data.get("author_name") or username
        first_line = text.split(". ")[0][:60].strip()

        print(f"    - X(트위터) 게시물 감지 (작성자: {author} @{username})")
        return {
            'url': canonical_url,
            'title': f"[X(트위터)] {author}: {first_line}",
            'content': text,
            'search_text': first_line  # 검색어 추출은 대괄호 접두어 없이 본문만 사용
        }
    except Exception as e:
        print(f"[-] 트위터 게시물 조회 중 에러 발생: {e}")
        return None

def strip_josa(word):
    """
    한글 단어 뒤에 붙는 대표적인 조사들을 지워 명사 원형만 남깁니다.
    """
    # 한글 명사 원형 보호를 위한 예외 명사 사전 대폭 강화
    protected_words = {
        "국가", "회의", "결과", "효과", "통과", "온도", "태도", "속도", "지도", "제도", "도로", "서로", "나이", "아이", "오이", "차이", 
        "주의", "정의", "합의", "평화", "대화", "변화", "문화", "영화", "전화", "의사", "교사", "판사", "검사", "조사", "수사", "인사",
        "감사", "역사", "회사", "행사", "공사", "기사", "식사", "상사", "고사", "대사", "천사", "박사", "석사", "학사", "유사", "묘사"
    }
    if word in protected_words:
        return word
    josa_suffixes = ["에서", "한테", "부터", "까지", "으로", "처럼", "하고", "이며", "은", "는", "이", "가", "을", "를", "의", "에", "와", "과", "도", "만", "랑", "며", "로"]
    for suffix in josa_suffixes:
        if word.endswith(suffix) and len(word) > len(suffix):
            return word[:-len(suffix)]
    return word

def extract_keywords_fast(title):
    """
    제목의 명사와 주요 키워드를 로컬 정규식 기반으로 빠르게 추출하여 검색어로 사용합니다.
    불필요한 generic 명사들을 필터링하고 조사(Josa)를 제거한 뒤 최대 10개의 단어를 키워드로 취합하여 검색 품질을 높입니다.
    """
    # 특수문자 제거
    cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s]', ' ', title)
    words = cleaned.split()
    
    # 팩트체크 검색어로서 유용하지 않은 일반 서술어/조사류/시간단어/의미없는 1글자 단어 필터링 사전 대폭 확장
    stopwords = [
        "오늘", "내일", "어제", "올해", "내년", "최근", "하루", "이틀", "이번", "주말", "평일", "휴일", "명절", 
        "기자", "뉴스", "보도", "착수", "개발", "기술", "경찰", "정부", "공고", "지원", "선정", "했다", "한다", "밝혔다", "적발", "검거", "조사",
        "및", "등", "더", "또", "속", "과", "와", "한", "그", "저", "요", "네", "아", "오", "제", "매", "수", "것", "등등",
        "진짜", "가짜", "충격", "결국", "의혹", "논란", "사실", "해명", "공개", "주장", "전면", "부인", "반박", "발표", "확인", "의문", "루머",
        "네티즌", "네티즌들", "커뮤니티", "누리꾼", "누리꾼들", "SNS", "인스타그램", "트위터", "유튜브", "영상", "사진", "포착", "근황", "공식",
        "입장", "발언", "논란이", "논란은", "의혹이", "의혹은", "충격적인", "발칵", "뒤집힌", "난리", "난리난"
    ]
    
    filtered = []
    for w in words:
        # 단어 길이가 1 이상이고 스톱워드가 아닌 경우 허용 ('불', '총', '핵' 등 1글자 중요 명사 구제)
        if len(w) >= 1 and w not in stopwords:
            cleaned_word = strip_josa(w)
            if len(cleaned_word) >= 1 and cleaned_word not in stopwords:
                filtered.append(cleaned_word)
            
    # 중복 제거 및 순서 보존
    seen = set()
    unique_filtered = []
    for w in filtered:
        if w not in seen:
            seen.add(w)
            unique_filtered.append(w)
            
    # 핵심 명사 최대 10개 선택 (이벤트 핵심 액션 단어 유실 방지)
    return unique_filtered[:10]

def call_gemini_api(prompt, response_mime_type=None, temperature=None, max_output_tokens=None):
    """
    Gemini API를 호출하는 공통 함수.
    gemini-2.5-flash를 우선 시도하고 실패하면 gemini-2.0-flash-lite로 폴백하며,
    최대 2회 재시도(지수 백오프 적용)를 지원하여 일시적 서버 오류나 할당량 초과에 대응합니다.
    인증 오류(401/403)는 즉시 중단하여 불필요한 API 호출을 방지합니다.
    """
    import time
    if not GEMINI_API_KEY or GEMINI_API_KEY.strip() == "" or GEMINI_API_KEY.strip() == "YOUR_GEMINI_API_KEY":
        print("[-] GEMINI_API_KEY가 설정되지 않았거나 기본값입니다.")
        return None
    
    # 사용할 모델 목록 (우선순위 순서)
    models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
    
    # 서버리스 환경에서는 타임아웃을 짧게 설정하여 Vercel 60초 제한에 대비
    request_timeout = 20 if IS_SERVERLESS else 25
    max_retries = 2  # 과도한 재시도 방지: 모델당 최대 2회
    
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY.strip()}"
        headers = {
            "Content-Type": "application/json"
        }
        
        generation_config = {}
        if response_mime_type:
            generation_config["responseMimeType"] = response_mime_type
        if temperature is not None:
            generation_config["temperature"] = temperature
        if max_output_tokens is not None:
            generation_config["maxOutputTokens"] = max_output_tokens
            
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }]
        }
        if generation_config:
            payload["generationConfig"] = generation_config
            
        backoff_factor = 1.5
        
        for attempt in range(max_retries):
            try:
                print(f"[★] Gemini API 호출 시도 ({model}, 시도 {attempt + 1}/{max_retries})...")
                resp = requests.post(url, headers=headers, json=payload, timeout=request_timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    try:
                        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    except (KeyError, IndexError) as pe:
                        print(f"[-] Gemini 응답 데이터 구조 오류: {pe}")
                        print(f"    응답 내용: {json.dumps(data, ensure_ascii=False)[:500]}")
                        break
                elif resp.status_code in [401, 403]:
                    # 인증 오류는 재시도해도 소용 없음 → 모든 모델에 대해 즉시 중단
                    print(f"[-] Gemini API 인증 실패 (HTTP {resp.status_code}): API 키가 유효하지 않거나 권한이 없습니다.")
                    print(f"    응답: {resp.text[:300]}")
                    return None
                elif resp.status_code == 429:
                    sleep_time = (backoff_factor ** attempt) * 2
                    print(f"[-] Gemini API Rate Limit (429) 감지. {sleep_time:.1f}초 후 재시도합니다...")
                    time.sleep(sleep_time)
                elif resp.status_code == 503:
                    # 503 = 모델 과부하 → 같은 모델 재시도해봐야 의미 없으므로 즉시 다음 폴백 모델로
                    print(f"[-] Gemini API 모델 과부하 (503: UNAVAILABLE). 즉시 다음 폴백 모델로 전환합니다...")
                    break
                elif resp.status_code in [500, 504]:
                    sleep_time = (backoff_factor ** attempt) * 1.5
                    print(f"[-] Gemini API 서버 오류 ({resp.status_code}). {sleep_time:.1f}초 후 재시도합니다...")
                    time.sleep(sleep_time)
                else:
                    print(f"[-] Gemini API 호출 에러 (HTTP {resp.status_code}): {resp.text[:300]}")
                    break
            except requests.exceptions.Timeout:
                print(f"[-] Gemini API 타임아웃 ({request_timeout}초 초과). 다음 모델로 전환합니다...")
                break  # 타임아웃 시 재시도하지 않고 다음 모델로
            except requests.exceptions.RequestException as e:
                sleep_time = (backoff_factor ** attempt) * 1.5
                print(f"[-] Gemini API 통신 오류 ({e}). {sleep_time:.1f}초 후 재시도합니다...")
                time.sleep(sleep_time)
                
    print("[-] 모든 Gemini API 모델 호출 시도가 실패했습니다.")
    return None

def fact_check_article_with_sources(target_title, target_content, sources, content_label="기사"):
    """
    검증 대상 기사(또는 SNS 게시물)와, 수집된 진짜 뉴스 참고 자료들을 상호 대조하여 가짜뉴스 판정 결과를 내립니다.
    """
    if not sources:
        return {
            "verdict": "SUSPICIOUS",
            "reason": "검색된 관련 신뢰 뉴스 기사가 전혀 없습니다. 신생 루머이거나 극히 폐쇄적인 커뮤니티성 허위 사실일 가능성이 높습니다.",
            "contradiction_score": 0.8,
            "claims_breakdown": []
        }

    # 실시간 처리 속도를 올리기 위해 기사 본문을 병렬로 크롤링합니다. (최대 3개)
    ref_contents = [None] * len(sources)
    
    def crawl_source(index, link):
        try:
            print(f"      - [참고 자료 {index+1}] 본문 크롤링 진행: {link}")
            # 참고 자료 크롤링의 경우 타임아웃을 타이트하게 잡아 지연을 최소화합니다.
            ref_art = scrape_url_content(link, timeout=3.5 if IS_SERVERLESS else 5.0)
            if ref_art and ref_art['content']:
                return ref_art['content'][:1200]
        except Exception as e:
            print(f"      - [참고 자료 {index+1}] 크롤링 실패: {e}")
        return ""

    links_to_crawl = [(i, s['link']) for i, s in enumerate(sources) if i < 3]
    
    if links_to_crawl:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_index = {executor.submit(crawl_source, i, link): i for i, link in links_to_crawl}
            for future in future_to_index:
                idx = future_to_index[future]
                try:
                    ref_contents[idx] = future.result()
                except Exception as e:
                    print(f"      - [참고 자료 {idx+1}] 스레드 실행 오류: {e}")
                    ref_contents[idx] = ""

    sources_text = ""
    for i, s in enumerate(sources):
        ref_body = ref_contents[i] if i < len(ref_contents) and ref_contents[i] else ""
        desc = ref_body if ref_body else s['description']
        sources_text += f"[참고 뉴스 {i+1}]\n제목: {s['title']}\n요약/본문 내용: {desc}\n출처 링크: {s['link']}\n\n"

    from datetime import datetime
    current_date = datetime.now().strftime("%Y년 %m월 %d일")

    prompt = (
        f"현재 날짜: {current_date}\n"
        "당신은 가짜 뉴스와 조작된 허위 기사를 가려내는 전문 팩트체커 AI입니다.\n"
        f"아래 제공된 [검증 대상 {content_label}]의 사실 관계와, 실시간 검색 및 크롤링을 통해 수집된 공식 [참고 뉴스 기사 목록]을 상호 비교하십시오.\n\n"
        f"[검증 대상 {content_label}]\n"
        f"제목: {target_title}\n"
        f"본문: {target_content[:1000]}\n\n"
        "[참고 뉴스 기사 목록]\n"
        f"{sources_text}\n"
        "검증 지침:\n"
        f"1. 참고 뉴스 목록과 비교했을 때, 검증 대상 {content_label}가 없는 사실을 임의로 창작했거나 상호 모순되는 주장을 하는지 판단하세요.\n"
        "2. 인물의 발언, 실제 사건 발생 여부, 통계 수치 등이 참고 기사와 다르게 왜곡되거나 허위로 작성되었는지 대조하세요.\n"
        "3. SNS/커뮤니티 글은 공식 뉴스 기사에 비해 왜곡, 루머, 과장이 섞이기 쉽습니다. 공식 기사에서 다루지 않은 단순 폭로나 미확인 주장은 'SUSPICIOUS'로 분류하고 사유를 상세히 서술하세요.\n"
        "4. 해외 기사 인용의 경우, 영어 및 해외 원본 자료와 국내 보도 자료를 상호 검증하여 실제 번역이나 인용 과정에서 왜곡이 있었는지도 면밀히 살펴봐 주세요.\n"
        "5. 판단 종류:\n"
        "   - REAL: 참고 뉴스들과 내용(사건, 수치, 발언)이 거의 일치하는 정상 보도 기사인 경우\n"
        "   - FAKE: 중요 팩트나 수치가 왜곡되었거나, 실제로 존재하지 않는 인물/사건을 조작 날조한 것이 명백한 경우\n"
        "   - SUSPICIOUS: 완전히 조작되지는 않았으나 다소 과장이 섞여 있거나, 검색 결과로 사실 확인이 어려워 추가 검증이 필요한 경우\n\n"
        "출력 포맷은 반드시 아래 JSON 구조 한 가지만 제공하세요. 다른 부가설명(마크다운 코드 블록 등)은 배제하고 중괄호로 시작해 중괄호로 끝나는 순수 JSON 문자열이어야 합니다.\n"
        "{\n"
        '  "verdict": "REAL" | "FAKE" | "SUSPICIOUS",\n'
        '  "reason": "참고 기사와 대조 분석한 팩트 체크 판단 근거 요약 (한글로 상세 작성)",\n'
        '  "contradiction_score": 0.0 ~ 1.0 (모순되거나 왜곡된 정도의 척도),\n'
        '  "claims_breakdown": [\n'
        '    {\n'
        '      "claim": "기사에서 식별된 핵심 주장 또는 팩트 요소 (예: 성수대교 남단 진입 램프에 9cm 단차 발생)",\n'
        '      "truth": "진실" | "거짓" | "판단유보",\n'
        '      "explanation": "이 주장/사실이 진실 또는 거짓인 이유와 대조한 참고 자료 근거 (상세 서술)"\n'
        '    }\n'
        '  ]\n'
        "}"
    )
    
    # 클라우드 Gemini API 연동 설정이 있는 경우 우선 사용 (초고속 판정)
    gemini_result = None
    if GEMINI_API_KEY and GEMINI_API_KEY.strip() and GEMINI_API_KEY.strip() != "YOUR_GEMINI_API_KEY":
        try:
            print("\n[★] 클라우드 Gemini API를 호출하여 정밀 팩트체크 분석을 수행합니다...")
            output = call_gemini_api(prompt, response_mime_type="application/json")
            if output:
                try:
                    res = json.loads(output)
                    if "claims_breakdown" not in res:
                        res["claims_breakdown"] = []
                    gemini_result = res
                except Exception as je:
                    print(f"[-] Gemini JSON 파싱 에러. RAW 응답:\n{output}\n")
                    match = re.search(r'\{.*\}', output, re.DOTALL)
                    if match:
                        res = json.loads(match.group(0))
                        if "claims_breakdown" not in res:
                            res["claims_breakdown"] = []
                        gemini_result = res
        except Exception as e:
            print(f"[-] Gemini API 분석 중 예외 발생: {e}")
            
    if gemini_result is not None:
        return gemini_result

    print("[-] Gemini API 연동 실패로 인해 로컬 Ollama 모델로 폴백(Fallback)하거나 즉시 유보합니다.")

    # 서버리스 환경에서는 localhost Ollama가 존재하지 않으므로 즉시 판정을 유보합니다.
    if IS_SERVERLESS:
        if not (GEMINI_API_KEY and GEMINI_API_KEY.strip() and GEMINI_API_KEY.strip() != "YOUR_GEMINI_API_KEY"):
            reason = "서버에 GEMINI_API_KEY 환경 변수가 설정되지 않아 2단계 LLM 정밀 분석을 수행할 수 없습니다. 배포 설정에서 환경 변수가 등록해 주세요."
        else:
            reason = "Gemini API 호출에 실패하여 최종 판정을 유보합니다. 잠시 후 다시 시도해 주세요."
        return {
            "verdict": "SUSPICIOUS",
            "reason": reason,
            "contradiction_score": 0.5,
            "claims_breakdown": []
        }

    # 로컬 Ollama 모델을 활용한 기존 폴백 로직
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_ctx": 4096
        }
    }
    
    try:
        resp = requests.post(OLLAMA_GENERATE_URL, json=payload, timeout=90)
        if resp.status_code == 200:
            output = resp.json().get("response", "").strip()
            
            # JSON만 파싱하기 위해 정규식 추출 시도
            match = re.search(r'\{.*\}', output, re.DOTALL)
            if match:
                json_str = match.group(0)
            else:
                json_str = output
                
            try:
                res = json.loads(json_str)
                if "claims_breakdown" not in res:
                    res["claims_breakdown"] = []
                return res
            except Exception as je:
                print(f"[-] JSON 파싱 에러 발생. RAW 응답:\n{output}\n")
                raise je
    except Exception as e:
        print(f"[-] RAG LLM 팩트체크 분석 중 에러: {e}")
        
    return {
        "verdict": "SUSPICIOUS",
        "reason": "LLM 분석 도중 기술적 오류가 발생하여 최종 판정을 유보합니다.",
        "contradiction_score": 0.5,
        "claims_breakdown": []
    }

def get_trained_nll_model():
    """
    real_news.json 코퍼스를 로드하여 70%는 학습용, 30%는 검증용으로 분할합니다.
    검증용 데이터의 NLL Loss를 기반으로 동적 임계값을 계산하여 데이터 희소성(Sparsity) 문제를 보정합니다.
    """
    print("\n[*] 1단계 NLL 통계 필터 로딩 및 학습 중...")
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        real_news_path = os.path.join(base_dir, "data", "real_news.json")
            
        with open(real_news_path, "r", encoding="utf-8") as f:
            real_data = json.load(f)
            
        real_corpus = []
        for art in real_data:
            tokens = custom_tokenize(art['title'] + " " + art['content'])
            real_corpus.append(tokens)
            
        # 70:30 학습/검증 분할
        import random
        random.seed(42)
        random.shuffle(real_corpus)
        
        train_size = int(len(real_corpus) * 0.7)
        train_corpus = real_corpus[:train_size]
        val_corpus = real_corpus[train_size:]
        
        lm = TrigramLanguageModel()
        lm.train(train_corpus)
        print(f"    - NLL 모델 학습 완료 (학습용 기사: {len(train_corpus)}개, 검증용 기사: {len(val_corpus)}개)")
        
        # 임계치는 '보지 못한(unseen) 진짜 뉴스'인 검증용 데이터에서 계산해야 합니다.
        # 이렇게 해야 데이터 희소성으로 인해 자연스럽게 발생하는 페널티 점수가 임계치에 올바르게 반영됩니다.
        losses = []
        for tokens in val_corpus:
            loss, _ = lm.calculate_sentence_loss(tokens)
            if loss > 0:
                losses.append(loss)
                
        avg_loss = sum(losses) / len(losses)
        variance = sum((x - avg_loss) ** 2 for x in losses) / len(losses)
        std_dev = math.sqrt(variance)
        threshold = avg_loss + (1.2 * std_dev) # 1.2 sigma (가짜뉴스 탐지율 99.11% 최적화 세팅)
        
        print(f"    - 동적 NLL 임계값 (Threshold) 설정 완료: {threshold:.4f} (검증셋 평균: {avg_loss:.4f}, 표준편차: {std_dev:.4f})")
        return lm, threshold
    except Exception as e:
        print(f"[-] NLL 모델 학습 중 에러 발생 (기본 임계값 5.6 사용): {e}")
        return None, 5.6

def load_nll_model():
    """
    Tries to load a pre-trained NLL model from the JSON cache file.
    If the cache does not exist, it trains the model and saves it.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    trained_model_path = os.path.join(base_dir, "data", "nll_model_trained.json")
    
    if os.path.exists(trained_model_path):
        print("\n[*] 1단계 NLL 통계 필터 로딩 중 (캐시된 모델 사용)...")
        try:
            import time
            from collections import Counter
            t0 = time.time()
            with open(trained_model_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            lm = TrigramLanguageModel()
            lm.total_words = data["total_words"]
            lm.vocab = set(data["vocab"])
            threshold = data["threshold"]
            
            lm.unigrams = Counter(data["unigrams"])
            lm.bigrams = Counter({(k.split("\t")[0], k.split("\t")[1]): v for k, v in data["bigrams"].items()})
            lm.trigrams = Counter({(k.split("\t")[0], k.split("\t")[1], k.split("\t")[2]): v for k, v in data["trigrams"].items()})
            
            print(f"    - 캐시된 NLL 모델 로드 완료 ({time.time() - t0:.3f}초 소요, 임계값: {threshold:.4f})")
            return lm, threshold
        except Exception as e:
            print(f"[-] 캐시된 NLL 모델 로드 중 에러 발생, 재학습을 시도합니다: {e}")
            
    # Fallback to training
    lm, threshold = get_trained_nll_model()
    
    # Save cache
    try:
        print("[*] NLL 모델 캐시 저장 중...")
        serialized = {
            "total_words": lm.total_words,
            "vocab": list(lm.vocab),
            "threshold": threshold,
            "unigrams": dict(lm.unigrams),
            "bigrams": {f"{k[0]}\t{k[1]}": v for k, v in lm.bigrams.items()},
            "trigrams": {f"{k[0]}\t{k[1]}\t{k[2]}": v for k, v in lm.trigrams.items()}
        }
        with open(trained_model_path, "w", encoding="utf-8") as f:
            json.dump(serialized, f, ensure_ascii=False)
        print(f"[+] NLL 모델 캐시 저장 완료: {trained_model_path}")
    except Exception as e:
        print(f"[-] NLL 모델 캐시 저장 실패: {e}")
        
    return lm, threshold


def generate_search_query_via_llm(title, content):
    """
    SNS나 커뮤니티 게시물처럼 비정형적이고 비격식적인 글에서
    교차 검증을 위한 최적의 뉴스 검색 쿼리(명사 위주 핵심 키워드)를 LLM을 통해 생성합니다.
    """
    if not GEMINI_API_KEY or GEMINI_API_KEY.strip() == "" or GEMINI_API_KEY.strip() == "YOUR_GEMINI_API_KEY":
        return None
    
    prompt = (
        "아래 비정형 게시글(SNS/커뮤니티)을 분석하여, 이 글에서 주장하는 핵심 사실 관계를 검증하기 위해 포털 뉴스 검색창에 입력할 최적의 검색 쿼리(키워드 2~3개)를 단 한 줄로 생성하십시오.\n"
        "지침:\n"
        "1. 불필요한 은어, 조사, 수식어는 배제하고 핵심 사건, 인물, 명사만 추출하세요.\n"
        "2. 다른 설명 없이 오직 공백으로 구분된 키워드들만 출력하세요.\n"
        "예: '#박세리 아버지가 결국 고소당했네요 진짜 충격입니다 ㅠㅠ' -> '박세리 아버지 고소'\n\n"
        f"제목: {title}\n"
        f"본문 일부: {content[:300]}\n"
        "검색어:"
    )
    
    try:
        output = call_gemini_api(prompt, temperature=0.0, max_output_tokens=20)
        if output:
            # Clean output from punctuation/markdown
            output = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', output)
            return " ".join(output.split())
    except Exception as e:
        print(f"[-] LLM 검색어 생성 실패: {e}")
    return None

def check_url_validity(url, nll_model=None, nll_threshold=5.6):
    """
    주어진 URL을 크롤링하여 팩트 체크를 전체 수행하는 핵심 파이프라인 함수
    1단계 NLL 통계 필터가 동작한 뒤, 의심 기사만 2단계 RAG-LLM 분석을 수행합니다.
    """
    print(f"\n[1] 입력받은 URL 크롤링 중...")
    print(f"    Target: {url}")
    # SNS 게시물(인스타그램/트위터)은 전용 스크레이퍼 사용
    sns_label = None
    if is_instagram_url(url):
        sns_label = "인스타그램 게시물"
        article = scrape_instagram_post(url)
    elif is_twitter_url(url):
        sns_label = "X(트위터) 게시물"
        article = scrape_twitter_post(url)
    else:
        article = scrape_url_content(url)

    if not article or not article['content']:
        print("[-] 본문 텍스트를 추출할 수 없거나 웹페이지 접근에 실패했습니다.")
        return None

    print(f"    - 기사 제목: {article['title']}")
    print(f"    - 본문 길이: {len(article['content'])} 자 추출 완료.")

    # === 1단계: NLL 통계 필터 검사 ===
    # SNS 본문은 뉴스 문체 코퍼스로 학습된 NLL 필터에 부적합하므로 건너뛰고 바로 2단계 검증
    nll_loss = None
    if sns_label:
        print("\n[1-5] SNS 게시물은 1단계 NLL 필터를 건너뛰고 2단계 정밀 팩트체크로 바로 진행합니다.")
    elif nll_model:
        print("\n[1-5] 1단계 NLL 통계 필터 분석 중...")
        tokens = custom_tokenize(article['title'] + " " + article['content'])
        nll_loss, _ = nll_model.calculate_sentence_loss(tokens)
        print(f"    - 계산된 NLL Loss: {nll_loss:.4f} (임계값: {nll_threshold:.4f})")
        
        if nll_loss < nll_threshold:
            print("    [★] NLL 점수가 임계값 미만입니다. 자연스러운 문장 구조를 가진 진짜 뉴스로 판단되어 패스합니다.")
            return {
                "verdict": "REAL",
                "reason": f"1단계 NLL 통계 필터 검사 결과, 기사 문맥 전이 확률 손실(NLL Loss: {nll_loss:.4f})이 정상 범위(임계값: {nll_threshold:.4f}) 이내입니다. 조작되었거나 왜곡된 가짜 뉴스일 가능성이 낮아 통과되었습니다.",
                "contradiction_score": 0.0,
                "target_title": article['title'],
                "target_url": url,
                "nll_loss": round(nll_loss, 4),
                "stage": 1,
                "sources": [],
                "claims_breakdown": []
            }
        else:
            print("    [!] NLL 점수가 임계값을 초과했습니다. 기사의 문맥 연결이 부자연스러워 2단계 정밀 팩트체크로 이관합니다.")
            
    else:
        print("\n[-] NLL 모델이 로드되지 않아 1단계를 건너뛰고 2단계로 바로 진행합니다.")
        
    # === 2단계: RAG-LLM 팩트체크 ===
    print("\n[2] 로컬 텍스트 분석 기반 핵심 검색 키워드 추출 중...")
    # SNS는 '[플랫폼] 유저명:' 접두어를 제외한 본문에서 키워드 추출
    search_base = article.get('search_text') or article['title']
    
    # SNS 또는 커뮤니티의 경우 비정형 데이터이므로 LLM 기반 검색 쿼리 생성을 먼저 시도합니다.
    search_query = None
    is_sns_or_community = bool(sns_label) or any(dom in url for dom in [
        "dcinside.com", "fmkorea.com", "ruliweb.com", "clien.net", "ppomppu.co.kr", 
        "instiz.net", "inven.co.kr", "todayhumor.co.kr", "mlbpark.donga.com", 
        "slrclub.com", "pann.nate.com", "bobaedream.co.kr", "theqoo.net", "instiz"
    ])
    
    if is_sns_or_community:
        print("    - SNS/커뮤니티 출처 탐지: 더 정밀한 검색을 위해 LLM 기반 검색 쿼리 생성을 시도합니다.")
        search_query = generate_search_query_via_llm(article['title'], article['content'])
        
    if not search_query:
        keywords = extract_keywords_fast(search_base)
        if not keywords:
            search_query = search_base[:15]
        else:
            search_query = " ".join(keywords)
            
    print(f"    - 추출된 검색어: '{search_query}'")
    
    print("\n[3] 실시간 포털 및 웹 검색 교차 검증 정보 수집 중...")
    # 실시간 처리 속도를 올리기 위해 기사 수를 3개로 제한 (네이버 뉴스 + DuckDuckGo 하이브리드)
    sources = fetch_hybrid_news(search_query, display_count=3)
    print(f"    - 수집된 신뢰 기사 개수: {len(sources)}개")
    for i, s in enumerate(sources):
        print(f"      ({i+1}) {s['title']} | {s['pubDate']}")
        
    print("\n[4] RAG-LLM 기반 상호 팩트체크 대조 분석 중...")
    content_label = sns_label or "기사"
    result = fact_check_article_with_sources(article['title'], article['content'], sources, content_label=content_label)
    
    # 입력 정보 병합
    result['target_title'] = article['title']
    result['target_url'] = url
    result['nll_loss'] = round(nll_loss, 4) if nll_loss else None
    result['stage'] = 2
    result['sources'] = sources
    
    return result

if __name__ == "__main__":
    # Prevent console encoding issues
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    # 1단계 NLL 모델 로딩 및 학습 (캐시 지원)
    nll_model, nll_threshold = load_nll_model()
    
    # 2. 테스트 구동
    if len(sys.argv) < 2:
        print("\n사용법: python fact_checker_by_url.py <검증할 뉴스 기사 URL>")
        print("💡 테스트용 기본 기사(실제 뉴스)로 시뮬레이션 구동합니다.")
        # 기본 테스트용 실제 네이버 뉴스
        test_url = "https://n.news.naver.com/mnews/article/001/0014782046" 
    else:
        test_url = sys.argv[1]
        
    final_verdict = check_url_validity(test_url, nll_model, nll_threshold)
    
    if final_verdict:
        print("\n=============================================")
        print("🛡️  가짜뉴스 실시간 탐지 결과")
        print("=============================================")
        print(f"▶ 검증 대상 기사: {final_verdict['target_title']}")
        print(f"▶ 탐지 경로 (Stage): {final_verdict['stage']}단계 필터")
        if 'nll_loss' in final_verdict and final_verdict['nll_loss']:
            print(f"▶ 문맥 손실값 (NLL Loss): {final_verdict['nll_loss']}")
        print(f"▶ 탐지 결과 (Verdict): {final_verdict['verdict']}")
        print(f"▶ 모순도 점수 (Score): {final_verdict['contradiction_score']}")
        print(f"▶ 분석 근거:")
        print(f"  {final_verdict['reason']}")
        print("=============================================")
