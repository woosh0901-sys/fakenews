import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import json

from backend_app import app, rate_limiter
from security_utils import (
    validate_url_safe,
    safe_http_get,
    sanitize_text,
    sanitize_gemini_output,
    MAX_URL_LENGTH,
    MAX_RESPONSE_SIZE
)

class TestSecurityHardening(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        # Reset in-memory rate limiter between test runs
        rate_limiter._requests.clear()

    # -------------------------------------------------------------
    # 1. Normal & Malicious URL / SSRF Tests
    # -------------------------------------------------------------
    def test_ssrf_disallowed_ips_and_schemes(self):
        """SSRF: 로컬, 사설망, 루프백, 클라우드 메타데이터 IP 및 비정상 스킴 차단 검증"""
        blocked_urls = [
            "http://127.0.0.1",
            "http://127.0.0.1:8000/secret",
            "http://localhost",
            "http://localhost:3000",
            "http://10.0.0.1",
            "http://192.168.0.1",
            "http://172.16.0.1",
            "http://169.254.169.254/latest/meta-data",
            "http://0.0.0.0",
            "http://[::1]",
            "file:///etc/passwd",
            "ftp://example.com/file",
            "gopher://example.com",
            "javascript:alert(1)",
            "data:text/html,<b>test</b>"
        ]
        for u in blocked_urls:
            is_safe, err = validate_url_safe(u)
            self.assertFalse(is_safe, f"URL이 차단되지 않음: {u}")
            self.assertTrue(len(err) > 0)

    def test_url_length_limit(self):
        """너무 긴 URL (> 2048자) 차단 검증"""
        long_url = "https://example.com/news/" + "a" * 2050
        is_safe, err = validate_url_safe(long_url)
        self.assertFalse(is_safe)
        self.assertIn("초과", err)

    def test_preview_endpoint_ssrf_block(self):
        """/api/preview 엔드포인트에서 SSRF 시도 시 400 Bad Request 차단 확인"""
        resp = self.client.post("/api/preview", json={"url": "http://127.0.0.1:8000"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("안전하지 않거나", resp.json()["detail"])

    def test_check_endpoint_ssrf_block(self):
        """/api/check 엔드포인트에서 SSRF 시도 시 400 Bad Request 차단 확인"""
        resp = self.client.post("/api/check", json={"url": "http://169.254.169.254/latest/meta-data"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("안전하지 않거나", resp.json()["detail"])

    # -------------------------------------------------------------
    # 2. Debug Endpoints Removal
    # -------------------------------------------------------------
    def test_debug_endpoints_removed(self):
        """민감정보 유출 위험이 있는 /api/debug/env, /api/debug/gemini 제거 확인 (404)"""
        resp_env = self.client.get("/api/debug/env")
        self.assertEqual(resp_env.status_code, 404)
        
        resp_gemini = self.client.get("/api/debug/gemini")
        self.assertEqual(resp_gemini.status_code, 404)

    # -------------------------------------------------------------
    # 3. Security Headers
    # -------------------------------------------------------------
    def test_security_headers_present(self):
        """보안 헤더(X-Content-Type-Options, X-Frame-Options 등) 응답 부착 확인"""
        resp = self.client.get("/api/stats")
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(resp.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(resp.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")

    # -------------------------------------------------------------
    # 4. Rate Limiting Tests
    # -------------------------------------------------------------
    def test_rate_limiting_check_endpoint(self):
        """/api/check 분당 5회 초과 시 429 Too Many Requests 반환 확인"""
        with patch("backend_app.validate_url_safe", return_value=(True, "")), \
             patch("backend_app.run_in_threadpool") as mock_run:
            mock_run.return_value = {
                "verdict": "REAL",
                "target_title": "테스트",
                "target_url": "https://example.com/1",
                "contradiction_score": 0.0,
                "reason": "테스트",
                "stage": 2,
                "sources": []
            }
            # 5회까지 성공
            for _ in range(5):
                res = self.client.post("/api/check", json={"url": "https://example.com/1"})
                self.assertNotEqual(res.status_code, 429)

            # 6회째 Rate Limit 도달
            res_exceeded = self.client.post("/api/check", json={"url": "https://example.com/1"})
            self.assertEqual(res_exceeded.status_code, 429)
            self.assertIn("너무 많은 요청", res_exceeded.json()["detail"])

    # -------------------------------------------------------------
    # 5. Prompt Injection & Output Sanitization
    # -------------------------------------------------------------
    def test_sanitize_gemini_output_with_anomalies(self):
        """비정상/악의적 Gemini 응답에 대한 스키마 검증 및 안전한 폴백 검증"""
        # Case A: Out-of-bound scores & invalid verdict
        raw_anomaly = {
            "verdict": "HACKED_VERDICT",
            "contradiction_score": 99.9,
            "evidence_quality": -5.0,
            "independent_source_count": -3,
            "reason": "<script>alert('xss')</script> 악의적 텍스트",
            "claims_breakdown": [
                {"claim": "<b>조작된 주장</b>", "truth": "UNKNOWN", "explanation": "설명"}
            ]
        }
        sanitized = sanitize_gemini_output(raw_anomaly, sources_count=3)
        self.assertEqual(sanitized["verdict"], "SUSPICIOUS")
        self.assertEqual(sanitized["contradiction_score"], 1.0)
        self.assertEqual(sanitized["evidence_quality"], 0.0)
        self.assertEqual(sanitized["independent_source_count"], 0)
        self.assertNotIn("<script>", sanitized["reason"])
        self.assertEqual(sanitized["claims_breakdown"][0]["truth"], "판단유보")
        self.assertNotIn("<b>", sanitized["claims_breakdown"][0]["claim"])

    # -------------------------------------------------------------
    # 6. Text Sanitization
    # -------------------------------------------------------------
    def test_sanitize_text(self):
        """악성 제어문자 및 HTML 태그 정제 테스트"""
        dirty = "<script>alert(1)</script>안녕하세요\x00\x08 반갑습니다."
        cleaned = sanitize_text(dirty)
        self.assertEqual(cleaned, "alert(1)안녕하세요 반갑습니다.")

if __name__ == "__main__":
    unittest.main()
