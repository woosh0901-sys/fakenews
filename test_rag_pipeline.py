import unittest
from fact_checker_by_url import (
    get_domain,
    classify_source,
    get_source_weight,
    text_similarity,
    rank_and_select_sources,
    fact_check_article_with_sources,
)

class TestRAGFactCheckingPipeline(unittest.TestCase):

    def test_domain_extraction(self):
        """URL 도메인 추출 및 www, 모바일 등 정규화 검증"""
        self.assertEqual(get_domain("https://www.yna.co.kr/view/AKR20240101"), "yna.co.kr")
        self.assertEqual(get_domain("http://m.news.naver.com/article/123"), "naver.com")
        self.assertEqual(get_domain("https://mofa.go.kr/press/release"), "mofa.go.kr")
        self.assertEqual(get_domain("https://kostat.go.kr/board.es"), "kostat.go.kr")
        self.assertEqual(get_domain("https://mobile.chosun.com/site/data/html_dir/"), "chosun.com")

    def test_source_classification_and_weights(self):
        """출처 유형 분류 (PRIMARY, WIRE / MAJOR, GENERAL, OTHER) 및 선택 가중치 검증"""
        # PRIMARY
        self.assertEqual(classify_source("https://www.korea.kr/news/policyNewsView.do"), "PRIMARY")
        self.assertEqual(classify_source("https://mofa.go.kr/press/release"), "PRIMARY")
        self.assertEqual(classify_source("https://scourt.go.kr/supreme/"), "PRIMARY")
        self.assertEqual(classify_source("https://who.int/news/item/123"), "PRIMARY")
        self.assertEqual(get_source_weight("https://mofa.go.kr"), 1.0)

        # WIRE / MAJOR NEWS
        self.assertEqual(classify_source("https://www.yna.co.kr/view/AKR"), "WIRE / MAJOR NEWS")
        self.assertEqual(classify_source("https://newsis.com/view/NIS"), "WIRE / MAJOR NEWS")
        self.assertEqual(classify_source("https://kbs.co.kr/news"), "WIRE / MAJOR NEWS")
        self.assertEqual(classify_source("https://chosun.com/national"), "WIRE / MAJOR NEWS")
        self.assertEqual(get_source_weight("https://yna.co.kr"), 0.85)

        # GENERAL NEWS
        self.assertEqual(classify_source("https://techm.kr/news/article"), "GENERAL NEWS")
        self.assertEqual(classify_source("https://inews24.com/view"), "GENERAL NEWS")
        self.assertEqual(get_source_weight("https://techm.kr/news/article"), 0.70)

        # OTHER
        self.assertEqual(classify_source("https://random-blog.xyz/post/1"), "OTHER")
        self.assertEqual(get_source_weight("https://random-blog.xyz"), 0.50)

    def test_case_1_syndicated_articles_deduplication(self):
        """테스트 1: 서로 다른 언론사가 같은 보도자료를 재인용 -> 독립 그룹으로 묶여 1건만 선별"""
        candidates = [
            {"title": "[속보] 정부, 2026년 청년 주거 지원 종합대책 공식 발표", "link": "https://media-a.com/news/1", "description": "대책 발표 내용...", "pubDate": "2026-08-10"},
            {"title": "정부, 2026년 청년 주거 지원 종합대책 공식 발표", "link": "https://media-b.com/news/2", "description": "대책 발표 내용...", "pubDate": "2026-08-10"},
            {"title": "정부 '2026년 청년 주거 지원 종합대책' 공식 발표", "link": "https://media-c.com/news/3", "description": "대책 발표 내용...", "pubDate": "2026-08-10"},
            {"title": "한국은행, 기준금리 0.25%p 인하 전격 결정", "link": "https://media-d.com/news/4", "description": "금리 인하...", "pubDate": "2026-08-10"},
        ]
        selected = rank_and_select_sources(candidates, max_sources=4, target_title="정부 청년 주거 대책")
        
        # 청년 주거 지원 대책 기사는 3개 언론사지만 동일 보도자료로 그룹화되어 1건만 대표로 선별되어야 함
        housing_sources = [s for s in selected if "청년 주거" in s["title"]]
        self.assertEqual(len(housing_sources), 1)
        self.assertGreaterEqual(housing_sources[0]["syndication_count"], 3)

    def test_case_2_primary_source_priority(self):
        """테스트 2: 공식 정부 자료(.go.kr) + 일반 언론 기사 -> 공식 자료를 PRIMARY로 최우선 선별"""
        candidates = [
            {"title": "일반 보도 기사 A", "link": "https://generalnews.com/a", "description": "내용", "pubDate": "2026-08-10"},
            {"title": "일반 보도 기사 B", "link": "https://anothernews.com/b", "description": "내용", "pubDate": "2026-08-10"},
            {"title": "보건복지부 공식 정책 보도자료", "link": "https://www.mohw.go.kr/board/123", "description": "공식 발표", "pubDate": "2026-08-10"},
            {"title": "일반 보도 기사 C", "link": "https://somemedia.com/c", "description": "내용", "pubDate": "2026-08-10"},
        ]
        selected = rank_and_select_sources(candidates, max_sources=3)
        self.assertTrue(any(s["source_type"] == "PRIMARY" for s in selected))
        self.assertEqual(selected[0]["domain"], "mohw.go.kr")

    def test_case_3_independent_sources_preserved(self):
        """테스트 3: 서로 다른 언론사가 독립적으로 확인한 사건 -> 다양성 확보하여 독립 출처 선별"""
        candidates = [
            {"title": "정부 AI 예산안 국회 통과", "link": "https://yna.co.kr/news/1", "description": "연합뉴스 보도", "pubDate": "2026-08-10"},
            {"title": "AI 핵심 반도체 R&D 세제혜택 확대 방안 확정", "link": "https://chosun.com/news/2", "description": "조선일보 심층분석", "pubDate": "2026-08-10"},
            {"title": "과기정통부 인공지능 윤리 가이드라인 발표", "link": "https://hani.co.kr/news/3", "description": "한겨레 보도", "pubDate": "2026-08-10"},
            {"title": "글로벌 빅테크 한국 AI 데이터센터 투자 협약", "link": "https://mk.co.kr/news/4", "description": "매일경제 취재", "pubDate": "2026-08-10"},
        ]
        selected = rank_and_select_sources(candidates, max_sources=4)
        self.assertEqual(len(selected), 4)
        unique_domains = set(s["domain"] for s in selected)
        self.assertEqual(len(unique_domains), 4)

    def test_case_4_single_source_handling(self):
        """테스트 4: 검색 결과가 하나뿐일 때 -> 파이프라인이 정상 작동하며 단일 근거로 처리"""
        candidates = [
            {"title": "단독 보도 기사 하나만 존재", "link": "https://single-source.com/1", "description": "내용", "pubDate": "2026-08-10"}
        ]
        selected = rank_and_select_sources(candidates, max_sources=4)
        self.assertEqual(len(selected), 1)

    def test_case_5_zero_sources_handling(self):
        """테스트 5: 검색 결과가 0개일 때 -> FAKE로 단정하지 않고 SUSPICIOUS 및 불일치 점수 0.5 반환"""
        res = fact_check_article_with_sources("테스트 제목", "테스트 본문", [])
        self.assertEqual(res["verdict"], "SUSPICIOUS")
        self.assertEqual(res["contradiction_score"], 0.5)
        self.assertEqual(res["evidence_quality"], 0.0)
        self.assertEqual(res["independent_source_count"], 0)
        self.assertFalse(res["primary_source_found"])
        self.assertIn("교차 검증", res["reason"])

    def test_case_7_domain_monopoly_prevention(self):
        """테스트 7: 동일 도메인의 기사가 다수 검색되어도 다른 도메인을 고루 선별"""
        candidates = [
            {"title": "A일보 기사 1: 사건 발단", "link": "https://dailynews.com/article/1", "description": "...", "pubDate": "2026-08-10"},
            {"title": "A일보 기사 2: 현장 인터뷰", "link": "https://dailynews.com/article/2", "description": "...", "pubDate": "2026-08-10"},
            {"title": "A일보 기사 3: 후속 취재", "link": "https://dailynews.com/article/3", "description": "...", "pubDate": "2026-08-10"},
            {"title": "B방송 뉴스: 공식 발표", "link": "https://kbs.co.kr/news/1", "description": "...", "pubDate": "2026-08-10"},
            {"title": "C통신사 속보: 입장문 전문", "link": "https://yna.co.kr/news/1", "description": "...", "pubDate": "2026-08-10"},
        ]
        selected = rank_and_select_sources(candidates, max_sources=3)
        domains = [s["domain"] for s in selected]
        self.assertLessEqual(domains.count("dailynews.com"), 1)
        self.assertIn("kbs.co.kr", domains)
        self.assertIn("yna.co.kr", domains)

    def test_case_8_naver_and_ddg_duplicate_url(self):
        """테스트 8: 동일 URL 또는 동일 기사 중복 제거"""
        candidates = [
            {"title": "한국은행 기준금리 동결", "link": "https://yna.co.kr/view/12345", "description": "설명 1", "pubDate": "2026-08-10"},
            {"title": "한국은행 기준금리 동결", "link": "https://yna.co.kr/view/12345", "description": "설명 2", "pubDate": "실시간 웹 검색"},
        ]
        selected = rank_and_select_sources(candidates, max_sources=4)
        self.assertEqual(len(selected), 1)

    def test_evidence_quality_calculation_logic(self):
        """테스트 9: Python 근거 품질 지표(evidence_quality) 산출 로직 검증"""
        from fact_checker_by_url import calculate_evidence_quality
        
        # 1. 0개 소스 -> 0.0
        self.assertEqual(calculate_evidence_quality([]), 0.0)
        
        # 2. 단일 일반 출처 1개 (GENERAL NEWS, weight 0.70)
        # avg_weight=0.70, indep=1/3, div=1.0, primary=0.0 -> (0.70*0.4)+(0.3333*0.3)+(1.0*0.15)+0.0 = 0.28+0.10+0.15 = 0.53
        single_general = [{"link": "https://techm.kr/1", "source_type": "GENERAL NEWS", "source_weight": 0.70, "domain": "techm.kr"}]
        eq_single = calculate_evidence_quality(single_general)
        self.assertAlmostEqual(eq_single, 0.53, places=1)
        
        # 3. 1차 자료(PRIMARY) 포함 3개 독립 출처 (PRIMARY + 2 MAJOR NEWS)
        # avg_weight=(1.0+0.85+0.85)/3=0.90, indep=3/3=1.0, div=3/3=1.0, primary=0.15
        # base_score=(0.90*0.4)+(1.0*0.3)+(1.0*0.15)+0.15 = 0.36+0.30+0.15+0.15 = 0.96
        rich_sources = [
            {"link": "https://mofa.go.kr/1", "source_type": "PRIMARY", "source_weight": 1.0, "domain": "mofa.go.kr"},
            {"link": "https://yna.co.kr/2", "source_type": "WIRE / MAJOR NEWS", "source_weight": 0.85, "domain": "yna.co.kr"},
            {"link": "https://kbs.co.kr/3", "source_type": "WIRE / MAJOR NEWS", "source_weight": 0.85, "domain": "kbs.co.kr"}
        ]
        eq_rich = calculate_evidence_quality(rich_sources)
        self.assertEqual(eq_rich, 0.96)
        self.assertLessEqual(eq_rich, 1.0)
        self.assertGreaterEqual(eq_rich, 0.0)

    def test_are_articles_duplicated_function(self):
        """테스트 10: 기사 중복/신디케이션 판별 함수(are_articles_duplicated) 검증"""
        from fact_checker_by_url import are_articles_duplicated
        
        art1 = {"title": "[속보] 정부, 2026년 청년 주거 종합대책 발표"}
        art2 = {"title": "정부, 2026년 청년 주거 종합대책 발표 (종합)"}
        art3 = {"title": "한국은행, 기준금리 동결 결정"}
        
        is_dup1, sim1 = are_articles_duplicated(art1, art2)
        self.assertTrue(is_dup1)
        self.assertGreaterEqual(sim1, 0.75)
        
        is_dup2, sim2 = are_articles_duplicated(art1, art3)
        self.assertFalse(is_dup2)
        self.assertLess(sim2, 0.5)

    def test_calculate_relevance_score_function(self):
        """테스트 11: 검색 결과 관련성 점수 함수(calculate_relevance_score) 검증"""
        from fact_checker_by_url import calculate_relevance_score
        
        target = {"title": "박세리 이사장, 부친 사문서위조 고소 관련 입장 발표"}
        cand_relevant = {"title": "박세리 부친 사문서위조 혐의 고소... 기자회견서 눈물"}
        cand_irrelevant = {"title": "손흥민 토트넘 프리미어리그 경기 일정 안내"}
        
        score_rel = calculate_relevance_score(target, cand_relevant)
        score_irrel = calculate_relevance_score(target, cand_irrelevant)
        
        self.assertGreater(score_rel, score_irrel)
        self.assertGreater(score_rel, 0.4)

if __name__ == "__main__":
    unittest.main()
