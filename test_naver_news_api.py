import unittest
from unittest.mock import patch, MagicMock
import requests
import json
import os

from naver_news_api import fetch_naver_news, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

class TestNaverNewsAPI(unittest.TestCase):
    """NAVER Cloud Platform NAVER API HUB 뉴스 검색 API 단위 테스트"""

    def setUp(self):
        self.client_id = "test_client_id"
        self.client_secret = "test_client_secret"
        self.query = "대한민국 대통령"
        self.display = 5

    @patch("naver_news_api.requests.get")
    def test_successful_request_and_parameters(self, mock_get):
        """정상 요청 시 NCP API HUB Endpoint, Headers, Params 검증"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "lastBuildDate": "Sun, 16 Aug 2026 15:00:00 +0900",
            "total": 100,
            "start": 1,
            "display": 5,
            "items": [
                {
                    "title": "<b>대한민국</b> <b>대통령</b> 관련 &quot;주요 뉴스&quot;",
                    "originallink": "https://news.example.com/article/1",
                    "link": "https://n.news.naver.com/mnews/article/1",
                    "description": "<b>대한민국</b> <b>대통령</b>이 &quot;새 정책&quot;을 발표했다.",
                    "pubDate": "Sun, 16 Aug 2026 14:00:00 +0900"
                },
                {
                    "title": "두 번째 기사 제목",
                    "originallink": "",
                    "link": "https://n.news.naver.com/mnews/article/2",
                    "description": "두 번째 기사 본문 요약",
                    "pubDate": "Sun, 16 Aug 2026 13:00:00 +0900"
                }
            ]
        }
        mock_get.return_value = mock_response

        results = fetch_naver_news(self.client_id, self.client_secret, self.query, display_count=self.display)

        # 1. requests.get 호출 인자 검증
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        called_url = args[0]
        called_headers = kwargs.get("headers", {})
        called_timeout = kwargs.get("timeout")

        # Endpoint 및 Query Parameter 검증
        self.assertTrue(called_url.startswith("https://naverapihub.apigw.ntruss.com/search/v1/news"))
        self.assertIn("display=5", called_url)
        self.assertIn("sort=sim", called_url)
        self.assertIn("query=", called_url)

        # Header 검증 (NCP API Gateway Key Headers)
        self.assertEqual(called_headers.get("X-NCP-APIGW-API-KEY-ID"), self.client_id)
        self.assertEqual(called_headers.get("X-NCP-APIGW-API-KEY"), self.client_secret)
        self.assertEqual(called_timeout, 3.0)

        # 2. 결과 파싱 검증
        self.assertEqual(len(results), 2)
        
        # 첫 번째 기사 (originallink 우선 + HTML 태그/엔티티 제거)
        item1 = results[0]
        self.assertEqual(item1["title"], '대한민국 대통령 관련 "주요 뉴스"')
        self.assertEqual(item1["description"], '대한민국 대통령이 "새 정책"을 발표했다.')
        self.assertEqual(item1["link"], "https://news.example.com/article/1")
        self.assertEqual(item1["pubDate"], "Sun, 16 Aug 2026 14:00:00 +0900")

        # 두 번째 기사 (originallink가 빈 문자열일 때 link fallback)
        item2 = results[1]
        self.assertEqual(item2["title"], "두 번째 기사 제목")
        self.assertEqual(item2["link"], "https://n.news.naver.com/mnews/article/2")

    @patch("naver_news_api.requests.get")
    def test_http_error_handling(self, mock_get):
        """잘못된 API Key 또는 권한 오류(HTTP 401/403/500) 시 안전한 에러 핸들링 및 빈 리스트 반환"""
        # 401 Unauthorized
        mock_response_401 = MagicMock()
        mock_response_401.status_code = 401
        mock_get.return_value = mock_response_401
        res = fetch_naver_news("invalid_id", "invalid_secret", self.query)
        self.assertEqual(res, [])

        # 403 Forbidden
        mock_response_403 = MagicMock()
        mock_response_403.status_code = 403
        mock_get.return_value = mock_response_403
        res = fetch_naver_news(self.client_id, self.client_secret, self.query)
        self.assertEqual(res, [])

        # 500 Server Error
        mock_response_500 = MagicMock()
        mock_response_500.status_code = 500
        mock_get.return_value = mock_response_500
        res = fetch_naver_news(self.client_id, self.client_secret, self.query)
        self.assertEqual(res, [])

    @patch("naver_news_api.requests.get")
    def test_timeout_exception_handling(self, mock_get):
        """API 호출 중 Timeout 발생 시 비정상 종료 없이 빈 리스트 반환"""
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")
        res = fetch_naver_news(self.client_id, self.client_secret, self.query)
        self.assertEqual(res, [])

    @patch("naver_news_api.requests.get")
    def test_connection_error_handling(self, mock_get):
        """API 서버 연결 실패 시 비정상 종료 없이 빈 리스트 반환"""
        mock_get.side_effect = requests.exceptions.ConnectionError("Failed to establish connection")
        res = fetch_naver_news(self.client_id, self.client_secret, self.query)
        self.assertEqual(res, [])

    @patch("naver_news_api.requests.get")
    def test_empty_search_results(self, mock_get):
        """검색 결과가 0건일 때 빈 리스트 반환"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "lastBuildDate": "Sun, 16 Aug 2026 15:00:00 +0900",
            "total": 0,
            "start": 1,
            "display": 0,
            "items": []
        }
        mock_get.return_value = mock_response

        res = fetch_naver_news(self.client_id, self.client_secret, "존재하지않는키워드xyz123")
        self.assertEqual(res, [])

    @patch("naver_news_api.requests.get")
    def test_json_decode_error_handling(self, mock_get):
        """API 응답이 올바른 JSON이 아닐 경우 예외 처리"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_get.return_value = mock_response

        res = fetch_naver_news(self.client_id, self.client_secret, self.query)
        self.assertEqual(res, [])

    def test_live_api_call_if_credentials_present(self):
        """실제 환경변수 키가 로드된 경우 라이브 호출 테스트 검증"""
        if NAVER_CLIENT_ID and NAVER_CLIENT_SECRET and NAVER_CLIENT_ID != "YOUR_CLIENT_ID":
            results = fetch_naver_news(NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, "대한민국", display_count=3)
            self.assertIsInstance(results, list)
            if len(results) > 0:
                item = results[0]
                self.assertIn("title", item)
                self.assertIn("link", item)
                self.assertIn("description", item)
                self.assertIn("pubDate", item)
                self.assertTrue(item["link"].startswith("http"))

if __name__ == "__main__":
    unittest.main()
