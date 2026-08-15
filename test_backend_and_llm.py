import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import json

from backend_app import app
from fact_checker_by_url import (
    fact_check_article_with_sources,
    check_url_validity
)

class TestBackendAndLLMIntegration(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_preview_endpoint(self):
        """미리보기 엔드포인트 동작 확인"""
        with patch("fact_checker_by_url.scrape_url_content") as mock_scrape:
            mock_scrape.return_value = {
                "title": "테스트 뉴스 기사",
                "content": "이것은 테스트용 본문 내용입니다.",
                "source": "테스트언론"
            }
            resp = self.client.post("/api/preview", json={"url": "https://news.example.com/123"})
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["title"], "테스트 뉴스 기사")
            self.assertIn("테스트용 본문", data["content"])

    def test_fact_check_with_conflicting_sources(self):
        """테스트 6: 참고 자료 간에 충돌이 있는 경우 LLM 프롬프트 생성 및 응답 검증"""
        sources = [
            {
                "title": "보건복지부 '비대면 진료 전면 허용 사실무근'",
                "link": "https://mohw.go.kr/release/1",
                "description": "복지부는 비대면 진료 전면 허용 보도는 사실과 다르다고 공식 해명했다.",
                "source_type": "PRIMARY",
                "domain": "mohw.go.kr",
                "syndication_count": 1
            },
            {
                "title": "정부, 다음달부터 비대면 진료 전면 허용 추진",
                "link": "https://news.example.com/2",
                "description": "정부가 다음달부터 전면 허용을 추진한다는 소식이 전해졌다.",
                "source_type": "GENERAL NEWS",
                "domain": "example.com",
                "syndication_count": 2
            }
        ]
        
        mock_llm_json = {
            "verdict": "SUSPICIOUS",
            "reason": "1차 공식 기관인 보건복지부 해명자료(사실무근)와 일반 언론 보도 내용이 상호 충돌하고 있어 사실 여부가 불분명하며 추가 확인이 필요합니다.",
            "contradiction_score": 0.75,
            "evidence_quality": 0.85,
            "independent_source_count": 2,
            "primary_source_found": True,
            "claims_breakdown": [
                {
                    "claim": "다음달부터 비대면 진료 전면 허용",
                    "truth": "판단유보",
                    "explanation": "주무부처인 보건복지부에서 공식적으로 부인하였으나 언론 보도가 혼재되어 있음."
                }
            ]
        }

        with patch("fact_checker_by_url.scrape_url_content") as mock_scrape, \
             patch("fact_checker_by_url.call_gemini_api") as mock_gemini, \
             patch("fact_checker_by_url.GEMINI_API_KEY", "mock_key"):
            
            mock_scrape.return_value = {"title": "크롤링 제목", "content": "크롤링 본문"}
            mock_gemini.return_value = json.dumps(mock_llm_json)
            
            result = fact_check_article_with_sources(
                target_title="다음달부터 비대면 진료 전면 허용된다",
                target_content="정부가 비대면 진료를 전면 허용하기로 결정했다는 주장이 제기됨.",
                sources=sources
            )
            
            self.assertEqual(result["verdict"], "SUSPICIOUS")
            self.assertEqual(result["contradiction_score"], 0.75)
            self.assertEqual(result["evidence_quality"], 0.85)
            self.assertEqual(result["independent_source_count"], 2)
            self.assertTrue(result["primary_source_found"])
            self.assertIn("충돌", result["reason"])

    def test_check_url_validity_full_flow(self):
        """check_url_validity 전체 파이프라인 흐름 및 반환 필드 무결성 검증"""
        mock_article = {
            "title": "정부 신규 AI 지원책 발표",
            "content": "정부는 신규 인공지능 지원책을 마련하였다. 상세 내용은 공식 발표 참고.",
            "url": "https://testnews.com/article/1"
        }
        mock_candidates = [
            {"title": "정부 신규 AI 지원책 발표", "link": "https://yna.co.kr/1", "description": "요약", "pubDate": "2026-08-10"},
            {"title": "과기정통부 AI 진흥계획 공표", "link": "https://msit.go.kr/2", "description": "공식자료", "pubDate": "2026-08-10"},
        ]
        mock_llm_json = {
            "verdict": "REAL",
            "reason": "과기정통부 공식 1차 자료 및 연합뉴스 보도와 핵심 내용이 일치합니다.",
            "contradiction_score": 0.05,
            "evidence_quality": 0.90,
            "independent_source_count": 2,
            "primary_source_found": True,
            "claims_breakdown": [
                {
                    "claim": "정부 신규 AI 지원책 발표",
                    "truth": "진실",
                    "explanation": "과기정통부 공식 보도자료와 일치함"
                }
            ]
        }

        with patch("fact_checker_by_url.scrape_url_content") as mock_scrape, \
             patch("fact_checker_by_url.fetch_hybrid_news") as mock_fetch, \
             patch("fact_checker_by_url.call_gemini_api") as mock_gemini, \
             patch("fact_checker_by_url.GEMINI_API_KEY", "mock_key"):
            
            mock_scrape.return_value = mock_article
            mock_fetch.return_value = mock_candidates
            mock_gemini.return_value = json.dumps(mock_llm_json)

            res = check_url_validity("https://testnews.com/article/1")
            
            # 필수 프론트엔드 및 백엔드 필드 검증
            self.assertIsNotNone(res)
            self.assertEqual(res["verdict"], "REAL")
            self.assertEqual(res["target_title"], "정부 신규 AI 지원책 발표")
            self.assertEqual(res["target_url"], "https://testnews.com/article/1")
            self.assertEqual(res["stage"], 2)
            self.assertIn("sources", res)
            self.assertIn("claims_breakdown", res)
            self.assertEqual(res["evidence_quality"], 0.90)
            self.assertEqual(res["independent_source_count"], 2)
            self.assertTrue(res["primary_source_found"])

if __name__ == "__main__":
    unittest.main()
