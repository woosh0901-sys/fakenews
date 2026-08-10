import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import Landing from "./Landing";
import { Trash2, ExternalLink, CheckCircle, Loader2, X, House } from "lucide-react";
import { verdictTone, truthTone } from "./verdict";
import useNarrow from "./useNarrow";

const API_BASE_URL = "/api";

export default function App() {
  // Timer references for memory cleanup
  const activeTimersRef = useRef([]);

  // 결과 섹션으로 스크롤하기 위한 참조
  const resultRef = useRef(null);

  // 좁은 화면에서는 입력창 placeholder가 잘리므로 짧은 문구로 바꾼다
  const isNarrow = useNarrow();

  // View state: 첫 접속은 랜딩, 검증 시작/대시보드 보기 클릭 시 대시보드로 전환
  const [view, setView] = useState("landing");

  // 랜딩에서 검증 시작 시: 분석 로딩 화면(스피너 + 기사 본문 스캔) 상태
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisDone, setAnalysisDone] = useState(false);
  const [preview, setPreview] = useState(null);

  // Data states
  const [urlInput, setUrlInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [history, setHistory] = useState([]);
  const [selectedItem, setSelectedItem] = useState(null);
  const [stats, setStats] = useState({
    total_checks: 0,
    real_count: 0,
    fake_count: 0,
    suspicious_count: 0
  });

  const [rankings, setRankings] = useState({ most_checked: [], top_fakes: [] });
  const [comments, setComments] = useState([]);
  const [commentAuthor, setCommentAuthor] = useState("");
  const [commentContent, setCommentContent] = useState("");

  // Persistent anonymous user identity
  const [userToken] = useState(() => {
    let token = localStorage.getItem("user_token");
    if (!token) {
      token = "user_" + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
      localStorage.setItem("user_token", token);
    }
    return token;
  });

  // Load rankings
  const loadRankings = async () => {
    try {
      const res = await axios.get(`${API_BASE_URL}/stats/rankings`);
      // 응답 형태가 예상과 달라도(배열 누락 등) 렌더가 죽지 않도록 정규화
      setRankings({
        most_checked: Array.isArray(res.data?.most_checked) ? res.data.most_checked : [],
        top_fakes: Array.isArray(res.data?.top_fakes) ? res.data.top_fakes : [],
      });
    } catch (err) {
      console.error("랭킹 로드 실패:", err);
    }
  };

  // Load history and stats
  const loadData = async () => {
    try {
      const [historyRes, statsRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/history`),
        axios.get(`${API_BASE_URL}/stats`)
      ]);
      setHistory(Array.isArray(historyRes.data) ? historyRes.data : []);
      if (statsRes.data && typeof statsRes.data === "object") {
        setStats((prev) => ({ ...prev, ...statsRes.data }));
      }
      loadRankings();
    } catch (err) {
      console.error("데이터 로드 오류:", err);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // 선택된 레포트의 댓글 로드 (DB에 저장되지 않은 결과는 id가 없으므로 요청하지 않는다)
  useEffect(() => {
    if (!selectedItem || selectedItem.id == null) {
      setComments([]);
      return;
    }
    let cancelled = false;
    axios
      .get(`${API_BASE_URL}/history/${selectedItem.id}/comments`)
      .then((res) => {
        if (!cancelled) setComments(Array.isArray(res.data) ? res.data : []);
      })
      .catch((err) => {
        console.error("댓글 로드 실패:", err);
        if (!cancelled) setComments([]);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedItem?.id]);

  // 결과가 열리면(검증 완료 / 히스토리 클릭) 결과 섹션을 화면 위로 가져온다
  useEffect(() => {
    if (view !== "dashboard" || !selectedItem) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const raf = requestAnimationFrame(() => {
      const el = resultRef.current;
      if (!el) return;
      el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
      el.focus({ preventScroll: true });
    });
    return () => cancelAnimationFrame(raf);
  }, [selectedItem?.id, selectedItem?.url, view]);

  // 실시간 탐지 현황에서 숫자를 눌러 히스토리를 판정별로 거른다 (null = 전체)
  const [verdictFilter, setVerdictFilter] = useState(null);

  // 마스트헤드 헤드라인 티커 — 가장 많이 검증된 기사 Top 5를 하나씩 올린다
  const [headlineIdx, setHeadlineIdx] = useState(0);
  const [headlinePaused, setHeadlinePaused] = useState(false);
  const headlineCount = rankings.most_checked?.length ?? 0;

  useEffect(() => {
    if (headlineCount < 2) return;
    const id = setInterval(() => {
      if (!headlinePaused && !document.hidden) {
        setHeadlineIdx((i) => (i + 1) % headlineCount);
      }
    }, 4000);
    return () => clearInterval(id);
  }, [headlineCount, headlinePaused]);

  // Cleanup all active timers on unmount
  useEffect(() => {
    return () => {
      activeTimersRef.current.forEach(clearTimeout);
      activeTimersRef.current = [];
    };
  }, []);

  // 검증 실행 (대시보드 폼에서 사용)
  const runCheck = async (targetUrl) => {
    if (loading || !targetUrl.trim()) return;

    // Clear any existing timers first
    activeTimersRef.current.forEach(clearTimeout);
    activeTimersRef.current = [];

    setLoading(true);
    setActiveStep(1);

    // Simulate steps visually to guide the user through the pipeline
    const t2 = setTimeout(() => setActiveStep(2), 1500);
    const t3 = setTimeout(() => setActiveStep(3), 3000);

    activeTimersRef.current = [t2, t3];

    try {
      const res = await axios.post(`${API_BASE_URL}/check`, { url: targetUrl }, { timeout: 90000 });
      activeTimersRef.current.forEach(clearTimeout);
      activeTimersRef.current = [];
      setActiveStep(4);

      const tSuccess = setTimeout(async () => {
        setUrlInput("");
        setLoading(false);
        await loadData();
        // /api/check 응답은 target_title/target_url 키를 사용하므로 표시용 필드로 정규화
        setSelectedItem({
          ...res.data,
          title: res.data.title ?? res.data.target_title,
          url: res.data.url ?? res.data.target_url,
        });
      }, 500);

      activeTimersRef.current.push(tSuccess);
    } catch (err) {
      activeTimersRef.current.forEach(clearTimeout);
      activeTimersRef.current = [];
      setLoading(false);
      const errMsg = err.response?.data?.detail || "탐지 분석 중 기술적 에러가 발생했습니다.";
      alert(errMsg);
    }
  };

  // Form submit handler
  const handleCheck = (e) => {
    e.preventDefault();
    runCheck(urlInput);
  };

  // 랜딩에서 검증 제출 → 분석 로딩 화면을 거쳐 대시보드로 전환 (Landing이 URL 형식을 미리 검사한다)
  const handleLandingSubmit = async (inputVal) => {
    const trimmed = inputVal.trim();
    if (loading || !trimmed) return;

    setUrlInput(trimmed);
    setPreview(null);
    setAnalysisDone(false);
    setAnalyzing(true);
    setLoading(true);

    // 로딩 화면에 띄울 기사 본문 미리보기 (실패해도 분석은 계속 진행)
    axios
      .post(`${API_BASE_URL}/preview`, { url: trimmed })
      .then((res) => setPreview(res.data))
      .catch(() => {});

    try {
      const res = await axios.post(`${API_BASE_URL}/check`, { url: trimmed });
      await loadData();

      // 완료 문구로 바뀐 것을 잠깐 보여준 뒤 대시보드로 넘어간다
      setAnalysisDone(true);
      setTimeout(() => {
        setSelectedItem({
          ...res.data,
          title: res.data.title ?? res.data.target_title,
          url: res.data.url ?? res.data.target_url,
        });
        setUrlInput("");
        setAnalyzing(false);
        setLoading(false);
        setView("dashboard");
      }, 1000);
    } catch (err) {
      setAnalyzing(false);
      setLoading(false);
      alert(err.response?.data?.detail || "탐지 분석 중 기술적 에러가 발생했습니다.");
    }
  };

  // Delete item handler
  const handleDelete = async (id, e) => {
    e.stopPropagation(); // Prevent row click select
    if (!confirm("정말 삭제하시겠습니까?")) return;
    try {
      await axios.delete(`${API_BASE_URL}/history/${id}`);
      if (selectedItem && selectedItem.id === id) {
        setSelectedItem(null);
      }
      loadData();
    } catch (err) {
      alert("삭제 실패");
    }
  };

  const handleAddComment = async (e) => {
    e.preventDefault();
    if (!commentContent.trim() || !selectedItem) return;

    if (selectedItem.id == null) {
      alert("데이터베이스에 저장되지 않은 검사 결과에는 댓글을 남길 수 없습니다. (Supabase 연결 상태나 환경 변수 설정 (.env)을 확인해 주세요.)");
      return;
    }

    const author = commentAuthor.trim() || "익명";
    try {
      const res = await axios.post(`${API_BASE_URL}/history/${selectedItem.id}/comments`, {
        author,
        content: commentContent,
        user_token: userToken
      });
      setComments([...comments, res.data]);
      setCommentContent("");
    } catch (err) {
      const errMsg = err.response?.data?.detail || err.message || "알 수 없는 에러";
      alert("댓글 저장 실패: " + errMsg);
    }
  };

  const handleDeleteComment = async (commentId) => {
    if (!selectedItem) return;
    if (!confirm("정말 이 댓글을 삭제하시겠습니까?")) return;
    try {
      await axios.delete(`${API_BASE_URL}/history/${selectedItem.id}/comments/${commentId}`, {
        params: { user_token: userToken }
      });
      setComments(comments.filter(c => c.id !== commentId));
    } catch (err) {
      const errMsg = err.response?.data?.detail || err.message || "삭제 실패";
      alert("댓글 삭제 실패: " + errMsg);
    }
  };

  // Loader steps definition
  const loaderSteps = [
    { label: "1. 본문 수집", desc: "웹페이지 크롤링 및 전처리" },
    { label: "2. 교차 검색", desc: "포털 API & 구글 웹 실시간 추적" },
    { label: "3. 사실 검증", desc: "Gemini 클라우드 사실관계 판정" }
  ];

  // 첫 화면: 랜딩 페이지
  if (view === "landing") {
    return (
      <Landing
        history={history}
        loading={loading}
        onSubmit={handleLandingSubmit}
        onOpenDashboard={() => setView("dashboard")}
        analyzing={analyzing}
        analysisDone={analysisDone}
        preview={preview}
      />
    );
  }

  const total = Math.max(Number(stats.total_checks) || 0, 1);
  const pct = (n) => ((Number(n) || 0) / total) * 100;

  const tone = selectedItem ? verdictTone(selectedItem.verdict) : null;
  const score = selectedItem ? Number(selectedItem.contradiction_score ?? 0) : 0;
  const sources = selectedItem?.sources ?? [];

  // 판정 필터 — 서버 통계와 같은 규칙(REAL/FAKE 외에는 모두 의심)으로 센다
  const matchesVerdict = (v) => {
    if (!verdictFilter) return true;
    if (verdictFilter === "SUSPICIOUS") return v !== "REAL" && v !== "FAKE";
    return v === verdictFilter;
  };
  const filteredHistory = history.filter((h) => matchesVerdict(h.verdict));

  const statItems = [
    { key: null, label: "총 검사", value: stats.total_checks, text: "text-neutral-900", rule: "border-neutral-900", bar: "bg-neutral-900" },
    { key: "REAL", label: "진짜", value: stats.real_count, text: "text-success-700", rule: "border-success-500", bar: "bg-success-500" },
    { key: "FAKE", label: "가짜", value: stats.fake_count, text: "text-error-700", rule: "border-error-500", bar: "bg-error-500" },
    { key: "SUSPICIOUS", label: "의심", value: stats.suspicious_count, text: "text-warning-700", rule: "border-warning-500", bar: "bg-warning-500" },
  ];
  const activeStat = statItems.find((s) => s.key === verdictFilter);

  // 마스트헤드 헤드라인 = 가장 많이 검증된 기사 Top 5를 순환
  const headlines = rankings.most_checked ?? [];
  const headlineAt = headlines.length ? headlineIdx % headlines.length : 0;
  const headline = headlines[headlineAt] ?? null;

  // 공통 클래스
  const kicker = "text-[11px] font-bold uppercase tracking-[0.18em]";
  const subKicker = `${kicker} text-neutral-500`;
  const inkButton =
    "shrink-0 bg-neutral-900 text-white px-6 md:px-8 py-3 text-[12px] font-bold uppercase tracking-[0.14em] hover:bg-brand-500 active:bg-brand-600 transition-colors disabled:opacity-30 disabled:cursor-not-allowed inline-flex items-center justify-center gap-2";
  const smallInput =
    "min-w-0 bg-transparent border-0 border-b border-neutral-300 px-0 py-2 text-sm placeholder:text-neutral-400 focus:outline-none focus:border-neutral-900 transition-colors";
  const editorialLink =
    "text-neutral-900 underline underline-offset-[3px] decoration-neutral-300 hover:decoration-brand-500 transition-colors";

  return (
    <div className="min-h-screen bg-neutral-0 text-neutral-900 font-sans">
      {/* 마스트헤드 — 홈 + 헤드라인(가장 많이 검증된 기사) */}
      <header className="sticky top-0 z-30 bg-neutral-0 border-b border-neutral-900">
        <div className="mx-auto w-full max-w-[1200px] px-6 md:px-10 h-14 flex items-center gap-4 md:gap-8">
          {/* 홈 — 데스크톱은 워드마크, 모바일은 아이콘(헤드라인 자리를 내준다) */}
          <button
            type="button"
            onClick={() => setView("landing")}
            title="메인 페이지로 이동"
            aria-label="메인 페이지로 이동"
            className="shrink-0 flex items-center text-brand-500 hover:text-neutral-900 transition-colors"
          >
            <span className="hidden md:inline text-[17px] font-black uppercase tracking-[-0.01em]">
              Fake News Defender
            </span>
            <span className="md:hidden inline-flex items-center justify-center w-9 h-9 -ml-2">
              <House size={20} strokeWidth={1.75} />
            </span>
          </button>

          {/* 헤드라인 — 가장 많이 검증된 기사 Top 5가 하나씩 올라온다 */}
          {headline ? (
            <button
              type="button"
              onClick={() => {
                const matched = history.find((h) => h.url === headline.url);
                if (matched) setSelectedItem(matched);
              }}
              onMouseEnter={() => setHeadlinePaused(true)}
              onMouseLeave={() => setHeadlinePaused(false)}
              onFocus={() => setHeadlinePaused(true)}
              onBlur={() => setHeadlinePaused(false)}
              title={headline.title}
              aria-label={`가장 많이 검증된 기사 ${headlineAt + 1}위: ${headline.title}`}
              className="flex-1 min-w-0 h-full flex items-center justify-center overflow-hidden group"
            >
              <span
                key={headlineAt}
                className="ticker-in flex items-center gap-2.5 min-w-0 max-w-full"
              >
                <span className="shrink-0 text-[11px] font-bold tabular-nums text-neutral-300">
                  {headlineAt + 1}
                </span>
                <span className="truncate text-[12px] md:text-[13px] text-neutral-700 group-hover:text-neutral-900 group-hover:underline underline-offset-[3px] decoration-neutral-300 transition-colors">
                  {headline.title}
                </span>
              </span>
            </button>
          ) : (
            <span className="flex-1" />
          )}

          <span className={`hidden lg:block shrink-0 ${kicker} text-neutral-400`}>Hybrid Fact-Checker</span>
        </div>
      </header>

      <div className="view-in mx-auto w-full max-w-[1200px] px-6 md:px-10 pb-28 lg:grid lg:grid-cols-[minmax(0,1fr)_260px] lg:gap-x-12">
      <main className="min-w-0 lg:col-start-1 lg:row-start-1">
        {/* §A 검증 입력 */}
        <section className="pt-8 md:pt-10">
          <h1 className={`${kicker} text-neutral-500`}>인공지능 교차 검증</h1>
          <form onSubmit={handleCheck} className="mt-3 flex items-end gap-3 md:gap-5">
            <input
              type="url"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder={isNarrow ? "기사 링크 붙여넣기" : "검증할 뉴스·인스타그램·X 링크를 붙여 넣으세요"}
              required
              disabled={loading}
              className="flex-1 min-w-0 bg-transparent border-0 border-b-2 border-neutral-900 px-0 py-3 text-base md:text-lg text-neutral-900 placeholder:text-neutral-400 focus:outline-none focus:border-brand-500 transition-colors disabled:opacity-40"
            />
            <button type="submit" disabled={loading} className={inkButton}>
              {loading ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  검증 중
                </>
              ) : (
                "검증"
              )}
            </button>
          </form>
          <p className="mt-2.5 text-[11px] leading-[1.6] text-neutral-500 max-w-[68ch]">
            실시간 웹 검색으로 수집한 보도와 대조해 판정합니다.
          </p>

          {/* 파이프라인 스테퍼 */}
          {loading && (
            <div className="mt-8 border-t border-neutral-200 pt-4">
              <div className="flex items-baseline justify-between gap-4">
                <span className="text-[11px] font-bold uppercase tracking-[0.16em] text-neutral-500">
                  하이브리드 탐지 파이프라인
                </span>
                <span className="text-[11px] font-bold uppercase tracking-[0.16em] text-neutral-900 animate-pulse">
                  실시간 구동 중
                </span>
              </div>
              <ol className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-x-8 gap-y-3">
                {loaderSteps.map((step, idx) => {
                  const isCompleted = activeStep > idx + 1;
                  const isActive = activeStep === idx + 1;
                  return (
                    <li
                      key={idx}
                      className={`border-t-2 pt-2 ${isActive || isCompleted ? "border-neutral-900" : "border-neutral-200"}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span
                          className={`text-[11px] font-bold tracking-[0.06em] ${
                            isActive ? "text-neutral-900" : isCompleted ? "text-success-700" : "text-neutral-400"
                          }`}
                        >
                          {step.label}
                        </span>
                        {isCompleted && <CheckCircle size={12} className="text-success-600 shrink-0" />}
                        {isActive && <Loader2 size={12} className="animate-spin text-neutral-900 shrink-0" />}
                      </div>
                      <p className="mt-1 text-[11px] leading-[1.5] text-neutral-500">{step.desc}</p>
                    </li>
                  );
                })}
              </ol>
            </div>
          )}
        </section>

        {/* §B 검증 결과 — 전체폭, 최상단 */}
        {selectedItem && (
          <section
            ref={resultRef}
            tabIndex={-1}
            aria-live="polite"
            className={`mt-10 scroll-mt-20 border-t-4 ${tone.rule} pt-5 focus:outline-none`}
          >
            <div className="flex items-start justify-between gap-4">
              <p className={`${subKicker} pt-1.5`}>정밀 진단 레포트</p>
              <div className="flex items-center gap-3 text-[11px] tabular-nums text-neutral-400">
                {selectedItem.id != null && <span>NO.{selectedItem.id}</span>}
                {selectedItem.created_at && <span>{new Date(selectedItem.created_at).toLocaleString()}</span>}
                {selectedItem.cached && <span className="uppercase tracking-[0.14em]">캐시</span>}
                <button
                  onClick={() => setSelectedItem(null)}
                  aria-label="레포트 닫기"
                  title="레포트 닫기"
                  className="-mr-2 shrink-0 inline-flex items-center justify-center w-10 h-10 text-neutral-400 hover:text-neutral-900 hover:bg-neutral-50 transition-colors"
                >
                  <X size={22} strokeWidth={1.75} />
                </button>
              </div>
            </div>

            {/* 판정어 + 모순율 */}
            <div className="mt-3 flex flex-wrap items-end justify-between gap-x-8 gap-y-3">
              <h2 className={`text-[36px] md:text-[48px] font-black leading-[0.9] tracking-[-0.04em] ${tone.text}`}>
                {tone.label}
              </h2>
              <div className="text-right">
                <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neutral-500">주장 모순율</p>
                <p className={`mt-1 text-[30px] md:text-[38px] font-bold tabular-nums leading-none ${tone.text}`}>
                  {(score * 100).toFixed(0)}
                  <span className="text-[16px] md:text-[20px] align-top">%</span>
                </p>
              </div>
            </div>

            <div className="mt-4 h-[3px] w-full bg-neutral-200">
              <div className={`h-full ${tone.bar} transition-all duration-500`} style={{ width: `${score * 100}%` }} />
            </div>

            <h3 className="mt-7 text-[22px] md:text-[28px] font-extrabold leading-[1.3] tracking-[-0.02em] max-w-[34ch]">
              {selectedItem.title}
            </h3>

            <p className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-neutral-500">
              <a href={selectedItem.url} target="_blank" rel="noreferrer" className={editorialLink}>
                원문 보기 <ExternalLink size={10} className="inline align-baseline" />
              </a>
              <span aria-hidden>·</span>
              <span>실시간 RAG 기사 대조</span>
              <span aria-hidden>·</span>
              <span className="tabular-nums">교차 출처 {sources.length}건</span>
            </p>

            {selectedItem.warning && (
              <p className="mt-6 border-l-2 border-warning-500 pl-5 text-[13px] leading-[1.7] text-warning-700 max-w-[68ch]">
                {selectedItem.warning}
              </p>
            )}

            {/* 리드 = 종합 소견 */}
            <p
              className={`mt-6 border-l-2 ${tone.rule} pl-5 text-[15px] md:text-base leading-[1.85] text-neutral-800 max-w-[68ch]`}
            >
              {selectedItem.reason}
            </p>

            {/* 요소별 세부 검증 */}
            {Array.isArray(selectedItem.claims_breakdown) && selectedItem.claims_breakdown.length > 0 && (
              <div className="mt-12 border-t border-neutral-200 pt-3">
                <h4 className={subKicker}>요소별 세부 검증</h4>
                <ol className="mt-2 divide-y divide-neutral-200">
                  {selectedItem.claims_breakdown.map((c, idx) => (
                    <li
                      key={idx}
                      className="grid grid-cols-[3.5rem_1fr] md:grid-cols-[5rem_1fr] gap-x-4 md:gap-x-6 py-5"
                    >
                      <span className={`pt-1 text-[11px] font-bold uppercase tracking-[0.14em] ${truthTone(c.truth)}`}>
                        {c.truth}
                      </span>
                      <div className="min-w-0">
                        <p className="text-[15px] font-bold leading-[1.5] text-neutral-900">{c.claim}</p>
                        <p className="mt-1.5 text-sm leading-[1.75] text-neutral-600 max-w-[68ch]">{c.explanation}</p>
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {/* 교차 검증 출처 */}
            {sources.length > 0 && (
              <div className="mt-12 border-t border-neutral-200 pt-3">
                <h4 className={subKicker}>교차 검증 출처</h4>
                <ol className="mt-2 divide-y divide-neutral-200">
                  {sources.map((src, i) => (
                    <li key={i} className="grid grid-cols-[1.75rem_1fr] gap-x-3 py-4">
                      <span className="text-[11px] font-bold tabular-nums text-neutral-300 pt-0.5">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <div className="min-w-0">
                        <a
                          href={src.link}
                          target="_blank"
                          rel="noreferrer"
                          className={`text-[14px] font-bold leading-snug ${editorialLink}`}
                        >
                          {src.title}
                          <ExternalLink size={10} className="inline ml-1 align-baseline text-neutral-400" />
                        </a>
                        <p className="mt-1 text-[12px] leading-[1.6] text-neutral-500 line-clamp-2">{src.description}</p>
                        <p className="mt-1 text-[11px] tabular-nums text-neutral-400">
                          {src.pubDate ?? src.pub_date ?? ""}
                        </p>
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {/* 공동 팩트체크 (댓글) */}
            <div className="mt-12 border-t border-neutral-200 pt-3">
              <h4 className={subKicker}>
                공동 팩트체크 <span className="tabular-nums">({comments.length})</span>
              </h4>

              {comments.length === 0 ? (
                <p className="mt-3 text-[12px] text-neutral-400">첫 의견을 남겨 보세요.</p>
              ) : (
                <ul className="mt-2 divide-y divide-neutral-200">
                  {comments.map((c, index) => (
                    <li key={c.id ?? index} className="py-4">
                      <div className="flex items-baseline justify-between gap-3">
                        <span className="text-[11px] font-bold uppercase tracking-[0.1em] text-neutral-900">
                          {c.author}
                        </span>
                        <span className="flex items-baseline gap-2 text-[11px] tabular-nums text-neutral-400">
                          {c.created_at && new Date(c.created_at).toLocaleDateString()}
                          {(c.user_token === userToken || !c.user_token) && (
                            <button
                              onClick={() => handleDeleteComment(c.id)}
                              title="댓글 삭제"
                              className="text-neutral-300 hover:text-error-600 transition-colors"
                            >
                              <X size={11} />
                            </button>
                          )}
                        </span>
                      </div>
                      <p className="mt-1.5 text-sm leading-[1.7] text-neutral-700 max-w-[68ch]">{c.content}</p>
                    </li>
                  ))}
                </ul>
              )}

              <form onSubmit={handleAddComment} className="mt-5 flex flex-wrap items-end gap-3">
                <input
                  type="text"
                  value={commentAuthor}
                  onChange={(e) => setCommentAuthor(e.target.value)}
                  placeholder="이름"
                  maxLength="15"
                  className={`w-28 shrink-0 ${smallInput}`}
                />
                <input
                  type="text"
                  value={commentContent}
                  onChange={(e) => setCommentContent(e.target.value)}
                  placeholder="공동 팩트체크 의견을 남겨 주세요"
                  required
                  className={`flex-1 min-w-[12rem] ${smallInput}`}
                />
                <button
                  type="submit"
                  disabled={!commentContent.trim()}
                  className="shrink-0 bg-neutral-900 text-white px-5 py-2 text-[11px] font-bold uppercase tracking-[0.14em] hover:bg-brand-500 active:bg-brand-600 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  등록
                </button>
              </form>
            </div>

            {/* 레포트 푸터 */}
            <div className="mt-12 border-t border-neutral-200 pt-4 flex items-center justify-between">
              <button
                onClick={() => setSelectedItem(null)}
                className="text-[11px] font-bold uppercase tracking-[0.12em] text-neutral-400 hover:text-neutral-900 underline underline-offset-4 decoration-neutral-200 transition-colors"
              >
                닫기
              </button>
              {selectedItem.id != null && (
                <button
                  onClick={(e) => handleDelete(selectedItem.id, e)}
                  className="text-[11px] font-bold uppercase tracking-[0.12em] text-neutral-400 hover:text-error-600 underline underline-offset-4 decoration-neutral-200 hover:decoration-error-600 transition-colors"
                >
                  <Trash2 size={12} className="inline mr-1.5 align-[-1px]" />
                  레포트 삭제
                </button>
              )}
            </div>
          </section>
        )}

        {/* §C 실시간 탐지 현황 */}
        <section className="mt-14 border-t border-neutral-900 pt-4">
          <h2 className={`${kicker} text-neutral-900`}>실시간 탐지 현황</h2>

          {/* 숫자를 누르면 히스토리가 해당 판정으로 걸러진다 */}
          <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 divide-x divide-neutral-200">
            {statItems.map((item, idx) => {
              const active = verdictFilter === item.key;
              const dimmed = verdictFilter !== null && !active;
              return (
                <button
                  key={item.label}
                  type="button"
                  onClick={() => setVerdictFilter(item.key)}
                  aria-pressed={active}
                  title={item.key ? `${item.label} 판정만 보기` : "전체 보기"}
                  className={`text-left group ${idx % 2 === 0 ? "pr-5 sm:px-5" : "pl-5 sm:px-5"} ${
                    idx === 0 ? "sm:pl-0" : ""
                  } ${idx >= 2 ? "mt-6 sm:mt-0" : ""}`}
                >
                  <p
                    className={`text-[11px] font-bold uppercase tracking-[0.16em] transition-colors ${
                      active ? "text-neutral-900" : "text-neutral-500 group-hover:text-neutral-900"
                    }`}
                  >
                    {item.label}
                  </p>
                  <p
                    className={`mt-1.5 inline-block pb-1 border-b-2 text-[26px] md:text-[30px] font-bold tabular-nums leading-none transition-colors ${
                      dimmed ? "text-neutral-300" : item.text
                    } ${active ? item.rule : "border-transparent"}`}
                  >
                    {item.value}
                  </p>
                </button>
              );
            })}
          </div>

          <div className="mt-5 flex h-[3px] w-full bg-neutral-200">
            <div className="bg-success-500" style={{ width: `${pct(stats.real_count)}%` }} />
            <div className="bg-error-500" style={{ width: `${pct(stats.fake_count)}%` }} />
            <div className="bg-warning-500" style={{ width: `${pct(stats.suspicious_count)}%` }} />
          </div>

        </section>
      </main>

      {/* 실시간 랭킹 레일 — 데스크톱은 우측 고정(자체 스크롤), 모바일은 히스토리 앞에 온다 */}
      <aside className="mt-14 lg:mt-0 lg:col-start-2 lg:row-start-1 lg:row-span-2 lg:self-start lg:sticky lg:top-[4.5rem] lg:pt-10 lg:max-h-[calc(100vh-5.5rem)] lg:overflow-y-auto lg:overscroll-contain lg:pr-1">
        <div className="border-t border-neutral-900 pt-4">
          <h2 className={`${kicker} text-neutral-900`}>실시간 랭킹</h2>

          <h3 className={`mt-4 ${kicker} text-neutral-500`}>가장 많이 검증된 기사</h3>
          {headlines.length === 0 ? (
            <p className="mt-2 text-[11px] text-neutral-400">검증 통계가 없습니다.</p>
          ) : (
            <ol className="mt-2 border-t border-neutral-200 divide-y divide-neutral-200">
              {headlines.map((item, idx) => (
                <li key={idx}>
                  <button
                    type="button"
                    onClick={() => {
                      const matched = history.find((h) => h.url === item.url);
                      if (matched) setSelectedItem(matched);
                    }}
                    className="w-full flex items-baseline gap-2.5 py-2.5 text-left group"
                  >
                    <span className="w-3 shrink-0 text-[11px] font-bold tabular-nums text-neutral-300">
                      {idx + 1}
                    </span>
                    <span className="flex-1 min-w-0 text-[12px] leading-[1.5] text-neutral-800 line-clamp-2 group-hover:underline underline-offset-[3px] decoration-neutral-300">
                      {item.title}
                    </span>
                    <span className="shrink-0 text-[11px] tabular-nums text-neutral-400">{item.count}회</span>
                  </button>
                </li>
              ))}
            </ol>
          )}

          <h3 className={`mt-8 ${kicker} text-neutral-500`}>모순율이 가장 높은 기사</h3>
          {(rankings.top_fakes ?? []).length === 0 ? (
            <p className="mt-2 text-[11px] text-neutral-400">검출된 거짓 기사가 없습니다.</p>
          ) : (
            <ol className="mt-2 border-t border-neutral-200 divide-y divide-neutral-200">
              {(rankings.top_fakes ?? []).map((item, idx) => {
                const t = verdictTone(item.verdict);
                return (
                  <li key={idx}>
                    <button
                      type="button"
                      onClick={() => {
                        const matched = history.find((h) => h.url === item.url);
                        if (matched) setSelectedItem(matched);
                      }}
                      className="w-full flex items-baseline gap-2.5 py-2.5 text-left group"
                    >
                      <span className="w-3 shrink-0 text-[11px] font-bold tabular-nums text-neutral-300">
                        {idx + 1}
                      </span>
                      <span className="flex-1 min-w-0 text-[12px] leading-[1.5] text-neutral-800 line-clamp-2 group-hover:underline underline-offset-[3px] decoration-neutral-300">
                        {item.title}
                      </span>
                      <span className={`shrink-0 text-[11px] tabular-nums font-bold ${t.text}`}>
                        {((Number(item.contradiction_score) || 0) * 100).toFixed(0)}%
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          )}
        </div>
      </aside>

      {/* 히스토리 — 데스크톱은 좌측 컬럼 아래쪽, 모바일은 랭킹 다음 */}
      <div className="min-w-0 lg:col-start-1 lg:row-start-2">
        {/* §E 검증 히스토리 */}
        <section className="mt-14 border-t border-neutral-900 pt-4">
          <div className="flex items-baseline justify-between gap-4">
            <div className="flex items-baseline gap-3 min-w-0">
              <h2 className={`${kicker} text-neutral-900 shrink-0`}>검증 히스토리</h2>
              {activeStat && activeStat.key && (
                <button
                  type="button"
                  onClick={() => setVerdictFilter(null)}
                  title="필터 해제"
                  className={`inline-flex items-center gap-1.5 text-[11px] font-bold tracking-[0.12em] ${activeStat.text} hover:text-neutral-900 transition-colors`}
                >
                  <span className={`h-[3px] w-4 shrink-0 ${activeStat.bar}`} />
                  {activeStat.label}만
                  <X size={12} />
                </button>
              )}
            </div>
            <span className="text-[11px] tabular-nums text-neutral-500 shrink-0">{filteredHistory.length}건</span>
          </div>

          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-y border-neutral-900">
                  <th className="py-2 pr-4 text-[11px] font-bold uppercase tracking-[0.16em] text-neutral-500">판정</th>
                  <th className="py-2 pr-4 text-[11px] font-bold uppercase tracking-[0.16em] text-neutral-500">기사</th>
                  <th className="py-2 pr-4 text-[11px] font-bold uppercase tracking-[0.16em] text-neutral-500 text-right whitespace-nowrap">
                    모순율
                  </th>
                  <th className="py-2 w-8" />
                </tr>
              </thead>
              <tbody>
                {filteredHistory.length === 0 ? (
                  <tr>
                    <td colSpan="4" className="py-16 text-center text-[13px] text-neutral-400">
                      {verdictFilter
                        ? `${activeStat?.label} 판정을 받은 기록이 없습니다.`
                        : "검증 기록이 없습니다. 위에 링크를 입력해 첫 기사를 검증해 보세요."}
                    </td>
                  </tr>
                ) : (
                  filteredHistory.map((item) => {
                    const isSelected = selectedItem?.id === item.id;
                    const t = verdictTone(item.verdict);
                    const s = Number(item.contradiction_score) || 0;
                    return (
                      <tr
                        key={item.id}
                        onClick={() => setSelectedItem(item)}
                        className={`border-b border-neutral-200 cursor-pointer hover:bg-neutral-50 transition-colors ${
                          isSelected ? "bg-neutral-50" : ""
                        }`}
                      >
                        <td
                          className={`py-4 pr-4 align-top whitespace-nowrap ${
                            isSelected ? "border-l-2 border-neutral-900 pl-3" : ""
                          }`}
                        >
                          <span
                            className={`inline-flex items-center gap-2 text-[11px] font-bold tracking-[0.12em] ${t.text}`}
                          >
                            <span className={`h-[3px] w-4 shrink-0 ${t.bar}`} />
                            {t.short}
                          </span>
                        </td>
                        <td className="py-4 pr-4 align-top max-w-0 w-full">
                          <span className="block truncate text-[14px] font-bold leading-snug text-neutral-900">
                            {item.title}
                          </span>
                          <span className="mt-0.5 block truncate text-[11px] text-neutral-400">
                            {item.url}
                            {item.created_at ? ` · ${new Date(item.created_at).toLocaleDateString()}` : ""}
                          </span>
                        </td>
                        <td
                          className={`py-4 pr-4 align-top text-right tabular-nums text-[13px] font-bold ${
                            s > 0.6 ? "text-error-700" : s > 0.2 ? "text-warning-700" : "text-success-700"
                          }`}
                        >
                          {(s * 100).toFixed(0)}%
                        </td>
                        <td className="py-4 align-top text-right">
                          <button
                            onClick={(e) => handleDelete(item.id, e)}
                            title="삭제"
                            className="p-1 text-neutral-300 hover:text-error-600 transition-colors"
                          >
                            <Trash2 size={14} />
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>

        <footer className="mt-20 border-t border-neutral-200 pt-4 flex items-baseline justify-between text-[11px] uppercase tracking-[0.16em] text-neutral-400">
          <span>Fake News Defender</span>
          <span>Powered by Gemini 2.5</span>
        </footer>
      </div>
      </div>
    </div>
  );
}
