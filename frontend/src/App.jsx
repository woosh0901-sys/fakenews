import React, { useState, useEffect } from "react";
import axios from "axios";
import { 
  Shield, 
  Search, 
  Trash2, 
  ExternalLink, 
  TrendingUp, 
  AlertTriangle, 
  CheckCircle, 
  HelpCircle, 
  Moon, 
  Sun, 
  Loader2, 
  X, 
  Database,
  History,
  Info,
  Layers,
  ArrowRight,
  TrendingDown,
  Globe,
  Clock
} from "lucide-react";

const API_BASE_URL = "http://127.0.0.1:8000/api";

export default function App() {
  // Theme state
  const [darkMode, setDarkMode] = useState(() => {
    return localStorage.getItem("theme") === "dark" || 
      (!localStorage.getItem("theme") && window.matchMedia("(prefers-color-scheme: dark)").matches);
  });

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
    suspicious_count: 0,
    avg_nll: 0,
    avg_contradiction_score: 0
  });

  // Apply theme class
  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add("dark");
      localStorage.setItem("theme", "dark");
    } else {
      document.documentElement.classList.remove("dark");
      localStorage.setItem("theme", "light");
    }
  }, [darkMode]);

  // Load history and stats
  const loadData = async () => {
    try {
      const [historyRes, statsRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/history`),
        axios.get(`${API_BASE_URL}/stats`)
      ]);
      setHistory(historyRes.data);
      setStats(statsRes.data);
    } catch (err) {
      console.error("데이터 로드 오류:", err);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Form submit handler
  const handleCheck = async (e) => {
    e.preventDefault();
    if (!urlInput.trim()) return;

    setLoading(true);
    setActiveStep(1);
    
    // Simulate steps visually to guide the user through the pipeline
    const timers = [];
    timers.push(setTimeout(() => setActiveStep(2), 1200));
    timers.push(setTimeout(() => setActiveStep(3), 2400));
    timers.push(setTimeout(() => setActiveStep(4), 3600));

    try {
      const res = await axios.post(`${API_BASE_URL}/check`, { url: urlInput });
      timers.forEach(clearTimeout);
      setActiveStep(5);
      
      // Delay slightly so user sees step 5 (success) before update
      setTimeout(async () => {
        setUrlInput("");
        setLoading(false);
        await loadData();
        setSelectedItem(res.data);
      }, 500);
      
    } catch (err) {
      timers.forEach(clearTimeout);
      setLoading(false);
      const errMsg = err.response?.data?.detail || "탐지 분석 중 기술적 에러가 발생했습니다.";
      alert(errMsg);
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

  // Badge helpers
  const getVerdictBadge = (verdict) => {
    switch (verdict) {
      case "REAL":
        return (
          <span className="flex items-center gap-1.5 w-fit bg-emerald-50 dark:bg-emerald-950/30 text-emerald-600 dark:text-emerald-400 text-xs px-2.5 py-1 rounded-full font-bold border border-emerald-200 dark:border-emerald-900/30">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            진짜 뉴스
          </span>
        );
      case "FAKE":
        return (
          <span className="flex items-center gap-1.5 w-fit bg-rose-50 dark:bg-rose-950/30 text-rose-600 dark:text-rose-400 text-xs px-2.5 py-1 rounded-full font-bold border border-rose-200 dark:border-rose-900/30">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse"></span>
            가짜 뉴스
          </span>
        );
      case "SUSPICIOUS":
      default:
        return (
          <span className="flex items-center gap-1.5 w-fit bg-amber-50 dark:bg-amber-950/30 text-amber-600 dark:text-amber-400 text-xs px-2.5 py-1 rounded-full font-bold border border-amber-200 dark:border-amber-900/30">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse"></span>
            의심/과장
          </span>
        );
    }
  };

  // Loader steps definition
  const loaderSteps = [
    { label: "1. 본문 수집", desc: "웹페이지 크롤링 및 전처리" },
    { label: "2. 문맥 분석", desc: "NLL 언어 모델 무결성 검증" },
    { label: "3. 교차 검색", desc: "포털 API & 구글 웹 실시간 추적" },
    { label: "4. 사실 검증", desc: "Gemini 클라우드 사실관계 판정" }
  ];

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-[#09090b] text-zinc-900 dark:text-zinc-100 flex transition-colors duration-200 font-sans">
      
      {/* Sidebar Layout */}
      <aside className="hidden lg:flex w-80 shrink-0 flex-col bg-white dark:bg-[#0c0c0f] border-r border-zinc-200 dark:border-zinc-800 p-6 sticky top-0 h-screen justify-between shadow-sm z-30 font-sans">
        <div className="space-y-8">
          
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-blue-600 dark:bg-blue-500 rounded-xl text-white shadow-md shadow-blue-500/10">
              <Shield size={24} />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 dark:from-blue-400 dark:via-indigo-400 dark:to-purple-400">
                Fake News Defender
              </h1>
              <p className="text-[10px] text-zinc-400 font-semibold tracking-wider uppercase mt-0.5">Hybrid Fact-Checker</p>
            </div>
          </div>

          {/* Stats Section */}
          <div className="space-y-4">
            <h2 className="text-xs font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-widest">실시간 탐지 현황</h2>
            
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-zinc-50 dark:bg-[#15151a] border border-zinc-200/60 dark:border-zinc-800 rounded-xl p-4 shadow-sm">
                <p className="text-[10px] text-zinc-400 font-bold uppercase">총 검사</p>
                <h3 className="text-xl font-bold font-mono mt-1 text-zinc-950 dark:text-zinc-50">{stats.total_checks}</h3>
              </div>
              <div className="bg-emerald-50/40 dark:bg-emerald-950/10 border border-emerald-100 dark:border-emerald-900/20 rounded-xl p-4 shadow-sm">
                <p className="text-[10px] text-emerald-600 dark:text-emerald-400 font-bold uppercase">진짜 뉴스</p>
                <h3 className="text-xl font-bold font-mono mt-1 text-emerald-600 dark:text-emerald-400">{stats.real_count}</h3>
              </div>
              <div className="bg-rose-50/40 dark:bg-rose-950/10 border border-rose-100 dark:border-rose-900/20 rounded-xl p-4 shadow-sm">
                <p className="text-[10px] text-rose-600 dark:text-rose-400 font-bold uppercase">가짜 뉴스</p>
                <h3 className="text-xl font-bold font-mono mt-1 text-rose-600 dark:text-rose-400">{stats.fake_count}</h3>
              </div>
              <div className="bg-amber-50/40 dark:bg-amber-950/10 border border-amber-100 dark:border-amber-900/20 rounded-xl p-4 shadow-sm">
                <p className="text-[10px] text-amber-600 dark:text-amber-400 font-bold uppercase">의심/과장</p>
                <h3 className="text-xl font-bold font-mono mt-1 text-amber-600 dark:text-amber-400">{stats.suspicious_count}</h3>
              </div>
            </div>

            {/* Performance Averages */}
            <div className="bg-zinc-50 dark:bg-[#15151a] border border-zinc-200/60 dark:border-zinc-800 rounded-xl p-4 space-y-3">
              <div className="flex justify-between items-center text-xs">
                <span className="text-zinc-500 dark:text-zinc-400 font-medium">평균 모순 점수</span>
                <span className="font-mono font-bold text-zinc-950 dark:text-zinc-50">{stats.avg_contradiction_score.toFixed(2)}</span>
              </div>
              <div className="w-full bg-zinc-200 dark:bg-zinc-800 h-1.5 rounded-full overflow-hidden">
                <div 
                  className="bg-blue-600 dark:bg-blue-500 h-full transition-all duration-500" 
                  style={{ width: `${stats.avg_contradiction_score * 100}%` }}
                />
              </div>
              <div className="flex justify-between items-center text-xs pt-1">
                <span className="text-zinc-500 dark:text-zinc-400 font-medium">평균 NLL 손실</span>
                <span className="font-mono font-bold text-zinc-950 dark:text-zinc-50">{stats.avg_nll.toFixed(2)}</span>
              </div>
            </div>

          </div>

        </div>

        {/* Sidebar Footer */}
        <div className="pt-4 border-t border-zinc-200 dark:border-zinc-800 flex items-center justify-between">
          <span className="text-xs text-zinc-400 dark:text-zinc-500 font-medium">Powered by Gemini 2.5</span>
          <button 
            onClick={() => setDarkMode(!darkMode)}
            className="p-2 border border-zinc-200 dark:border-zinc-800 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors text-zinc-500 dark:text-zinc-400"
          >
            {darkMode ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
      </aside>

      {/* Main Content Pane */}
      <div className="flex-1 flex flex-col min-w-0">
        
        {/* Mobile Header */}
        <header className="lg:hidden flex justify-between items-center px-6 py-4 border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0c0f] z-20">
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-blue-600 rounded-lg text-white">
              <Shield size={18} />
            </div>
            <span className="font-bold text-sm">Fake News Defender</span>
          </div>
          <button 
            onClick={() => setDarkMode(!darkMode)}
            className="p-2 border border-zinc-200 dark:border-zinc-800 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800"
          >
            {darkMode ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </header>

        {/* Content Wrapper */}
        <div className="flex-1 flex flex-col xl:flex-row overflow-x-hidden min-h-0">
          
          {/* Dashboard Body (Left/Center) */}
          <div className={`flex-1 p-6 space-y-6 overflow-y-auto max-w-full ${selectedItem ? "xl:w-2/3" : "w-full"} transition-all duration-300`}>
            
            {/* Search/URL Input Box - Sleek Google-Search style */}
            <section className="bg-white dark:bg-[#0c0c0f] border border-zinc-200 dark:border-zinc-800/80 rounded-2xl p-6 shadow-sm relative overflow-hidden">
              <div className="absolute top-0 left-0 w-full h-[3px] bg-gradient-to-r from-blue-500 via-indigo-500 to-purple-500"></div>
              
              <div className="max-w-2xl">
                <h2 className="text-xl font-bold tracking-tight text-zinc-950 dark:text-zinc-50">인공지능 교차 검증 시작하기</h2>
                <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1 font-medium">분석할 신문 기사나 SNS 보도 주소(URL)를 입력하면 1차 통계 문맥 검사 및 2차 실시간 웹 보도 대조를 진행합니다.</p>
              </div>

              <form onSubmit={handleCheck} className="flex gap-2.5 mt-5">
                <div className="relative flex-1">
                  <input 
                    type="url" 
                    value={urlInput}
                    onChange={(e) => setUrlInput(e.target.value)}
                    placeholder="검증하려는 기사 링크(https://...)를 입력해 주세요."
                    required
                    disabled={loading}
                    className="w-full bg-zinc-50 dark:bg-[#09090b] border border-zinc-200 dark:border-zinc-800 rounded-xl pl-11 pr-4 py-3.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500 transition-all text-zinc-950 dark:text-zinc-100 shadow-inner"
                  />
                  <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-400" />
                </div>
                <button 
                  type="submit"
                  disabled={loading}
                  className="bg-blue-600 hover:bg-blue-700 text-white rounded-xl px-7 py-3.5 font-bold transition-all shadow-sm shadow-blue-500/10 disabled:opacity-40 disabled:cursor-not-allowed text-sm shrink-0 flex items-center justify-center gap-1.5"
                >
                  {loading ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      검색 중
                    </>
                  ) : (
                    "신뢰도 검증"
                  )}
                </button>
              </form>

              {/* Dynamic Loading Timeline/Stepper */}
              {loading && (
                <div className="mt-6 pt-6 border-t border-zinc-100 dark:border-zinc-800/80 space-y-4">
                  <div className="flex items-center justify-between text-xs font-bold text-zinc-400 uppercase tracking-widest">
                    <span>하이브리드 탐지 파이프라인 분석 단계</span>
                    <span className="text-blue-500 dark:text-blue-400 flex items-center gap-1.5 animate-pulse">
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
                      실시간 구동 중
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    {loaderSteps.map((step, idx) => {
                      const isCompleted = activeStep > idx + 1;
                      const isActive = activeStep === idx + 1;
                      return (
                        <div 
                          key={idx}
                          className={`border rounded-xl p-3.5 transition-all duration-300 flex flex-col justify-between ${
                            isActive 
                              ? "bg-blue-50/50 dark:bg-blue-950/10 border-blue-500/50 dark:border-blue-500/30 shadow-[0_0_15px_rgba(59,130,246,0.05)]" 
                              : isCompleted
                                ? "bg-zinc-50/50 dark:bg-zinc-900/30 border-emerald-500/30 dark:border-emerald-500/20"
                                : "bg-zinc-50/30 dark:bg-zinc-900/10 border-zinc-200 dark:border-zinc-800/60 opacity-60"
                          }`}
                        >
                          <div className="flex justify-between items-center">
                            <span className={`text-[10px] font-bold uppercase tracking-wider ${
                              isActive ? "text-blue-600 dark:text-blue-400" : isCompleted ? "text-emerald-600 dark:text-emerald-400" : "text-zinc-400"
                            }`}>
                              {step.label}
                            </span>
                            {isCompleted && (
                              <CheckCircle size={14} className="text-emerald-500 shrink-0" />
                            )}
                            {isActive && (
                              <Loader2 size={14} className="animate-spin text-blue-500 shrink-0" />
                            )}
                          </div>
                          <p className="text-xs text-zinc-500 dark:text-zinc-400 font-medium mt-1">{step.desc}</p>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </section>

            {/* History Table Container */}
            <section className="bg-white dark:bg-[#0c0c0f] border border-zinc-200 dark:border-zinc-800/80 rounded-2xl shadow-sm overflow-hidden">
              <div className="p-5 border-b border-zinc-200 dark:border-zinc-800/60 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <History size={18} className="text-zinc-400" />
                  <h2 className="text-md font-bold tracking-tight text-zinc-950 dark:text-zinc-50">검증 히스토리</h2>
                </div>
                <span className="text-xs font-mono bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400 px-2 py-0.5 rounded-md font-bold">
                  기록 수: {history.length}건
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm whitespace-nowrap">
                  <thead className="bg-zinc-50 dark:bg-zinc-900/20 text-zinc-500 dark:text-zinc-400 border-b border-zinc-200 dark:border-zinc-800">
                    <tr>
                      <th className="p-4 font-bold text-xs uppercase tracking-wider">판정 결과</th>
                      <th className="p-4 font-bold text-xs uppercase tracking-wider">기사 제목 / 주소</th>
                      <th className="p-4 font-bold text-xs uppercase tracking-wider text-center">검사 단계</th>
                      <th className="p-4 font-bold text-xs uppercase tracking-wider text-center">모순 점수</th>
                      <th className="p-4 font-bold text-xs uppercase tracking-wider text-center">NLL 손실</th>
                      <th className="p-4 font-bold text-xs uppercase tracking-wider text-right">삭제</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800/60">
                    {history.length === 0 ? (
                      <tr>
                        <td colSpan="6" className="p-12 text-center text-zinc-500 dark:text-zinc-400 font-medium">
                          검증 기록이 존재하지 않습니다. 뉴스 링크를 입력하여 신뢰도를 판정해 보세요.
                        </td>
                      </tr>
                    ) : (
                      history.map((item) => {
                        const isSelected = selectedItem?.id === item.id;
                        return (
                          <tr 
                            key={item.id}
                            onClick={() => setSelectedItem(item)}
                            className={`hover:bg-zinc-50/50 dark:hover:bg-zinc-900/20 cursor-pointer transition-colors ${
                              isSelected ? "bg-blue-50/30 dark:bg-blue-950/10 hover:bg-blue-50/40 dark:hover:bg-blue-950/20" : ""
                            }`}
                          >
                            <td className="p-4">{getVerdictBadge(item.verdict)}</td>
                            <td className="p-4 max-w-sm md:max-w-md truncate">
                              <span className="block text-zinc-950 dark:text-zinc-50 font-bold leading-tight truncate">{item.title}</span>
                              <span className="text-xs text-zinc-400 font-medium truncate block mt-0.5 max-w-xs md:max-w-md">{item.url}</span>
                            </td>
                            <td className="p-4 text-center">
                              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                                item.stage === 1 
                                  ? "bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400"
                                  : "bg-purple-100/60 dark:bg-purple-950/20 text-purple-700 dark:text-purple-400"
                              }`}>
                                {item.stage === 1 ? "1단계 통과" : "2단계 정밀"}
                              </span>
                            </td>
                            <td className="p-4 text-center font-mono font-bold text-xs">
                              <div className="flex items-center justify-center gap-1.5">
                                <span className={item.contradiction_score > 0.6 ? "text-rose-500" : item.contradiction_score > 0.2 ? "text-orange-400" : "text-emerald-500"}>
                                  {item.contradiction_score.toFixed(2)}
                                </span>
                              </div>
                            </td>
                            <td className="p-4 text-center font-mono text-zinc-500 dark:text-zinc-400 text-xs">
                              {item.nll_loss ? item.nll_loss.toFixed(4) : "-"}
                            </td>
                            <td className="p-4 text-right">
                              <button 
                                onClick={(e) => handleDelete(item.id, e)}
                                className="text-zinc-400 hover:text-rose-500 p-1.5 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800/80 transition-colors"
                              >
                                <Trash2 size={15} />
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

          </div>

          {/* Details Diagnostic Slide-over Panel (Right) */}
          {selectedItem && (
            <div className="w-full xl:w-[450px] shrink-0 bg-white dark:bg-[#0c0c0f] border-t xl:border-t-0 xl:border-l border-zinc-200 dark:border-zinc-800 p-6 space-y-6 overflow-y-auto z-20 shadow-lg relative flex flex-col justify-between">
              
              <div className="space-y-6">
                
                {/* Panel Header */}
                <div className="flex justify-between items-start border-b border-zinc-200 dark:border-zinc-800/80 pb-4">
                  <div className="space-y-1">
                    <p className="text-[10px] font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-widest">정밀 진단 레포트</p>
                    <div className="flex items-center gap-2">
                      {getVerdictBadge(selectedItem.verdict)}
                      <span className="text-xs bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400 px-2 py-0.5 rounded font-mono font-bold">
                        #{selectedItem.id}
                      </span>
                    </div>
                  </div>
                  <button 
                    onClick={() => setSelectedItem(null)}
                    className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 p-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-colors border border-zinc-200 dark:border-zinc-800"
                  >
                    <X size={16} />
                  </button>
                </div>

                {/* Article info block */}
                <div className="space-y-2">
                  <h3 className="text-md font-bold tracking-tight text-zinc-950 dark:text-zinc-50 leading-snug">
                    {selectedItem.title}
                  </h3>
                  <div className="flex flex-wrap gap-x-4 gap-y-1">
                    <a 
                      href={selectedItem.url} 
                      target="_blank" 
                      rel="noreferrer"
                      className="flex items-center gap-1.5 text-xs text-blue-600 dark:text-blue-400 hover:underline font-bold"
                    >
                      <Globe size={12} /> 원문 보도 보기 <ExternalLink size={10} />
                    </a>
                    {selectedItem.created_at && (
                      <span className="text-[11px] text-zinc-400 font-semibold flex items-center gap-1">
                        <Clock size={12} /> {new Date(selectedItem.created_at).toLocaleString()}
                      </span>
                    )}
                  </div>
                </div>

                {/* Diagnostic Meters */}
                <div className="grid grid-cols-2 gap-3.5">
                  <div className="bg-zinc-50 dark:bg-[#15151a] border border-zinc-200/60 dark:border-zinc-800 rounded-xl p-4 shadow-sm space-y-1">
                    <p className="text-[10px] text-zinc-400 dark:text-zinc-500 font-bold uppercase tracking-wider">주장 모순율</p>
                    <div className="flex items-baseline gap-1 pt-1">
                      <span className={`text-2xl font-bold font-mono ${
                        selectedItem.contradiction_score > 0.6 ? "text-rose-500" : selectedItem.contradiction_score > 0.2 ? "text-orange-400" : "text-emerald-500"
                      }`}>
                        {(selectedItem.contradiction_score * 100).toFixed(0)}%
                      </span>
                    </div>
                    {/* Progress Bar inside panel */}
                    <div className="w-full bg-zinc-200 dark:bg-zinc-800 h-1.5 rounded-full mt-2.5 overflow-hidden">
                      <div 
                        className={`h-full transition-all duration-500 ${
                          selectedItem.contradiction_score > 0.6 
                            ? "bg-rose-500" 
                            : selectedItem.contradiction_score > 0.2 
                              ? "bg-orange-400" 
                              : "bg-emerald-500"
                        }`}
                        style={{ width: `${selectedItem.contradiction_score * 100}%` }}
                      />
                    </div>
                  </div>

                  <div className="bg-zinc-50 dark:bg-[#15151a] border border-zinc-200/60 dark:border-zinc-800 rounded-xl p-4 shadow-sm space-y-1">
                    <p className="text-[10px] text-zinc-400 dark:text-zinc-500 font-bold uppercase tracking-wider">NLL 손실 확률</p>
                    <div className="flex items-baseline gap-1 pt-1">
                      <span className="text-2xl font-bold font-mono text-zinc-900 dark:text-zinc-100">
                        {selectedItem.nll_loss ? selectedItem.nll_loss.toFixed(2) : "-"}
                      </span>
                    </div>
                    <span className="text-[9px] text-zinc-400 font-bold block mt-3">
                      {selectedItem.stage === 1 ? "1단계 고속 통과" : "2단계 심층 대조"}
                    </span>
                  </div>
                </div>

                {/* Verdict explanation card */}
                <div className="space-y-2">
                  <h4 className="text-[10px] font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-widest flex items-center gap-1.5">
                    <Info size={14} className="text-zinc-400" /> 종합 분석 소견
                  </h4>
                  <div className="bg-zinc-50 dark:bg-[#15151a] border border-zinc-200 dark:border-zinc-800 rounded-xl p-4 text-xs text-zinc-700 dark:text-zinc-300 leading-relaxed font-semibold">
                    {selectedItem.reason}
                  </div>
                </div>

                {/* Search references list */}
                {selectedItem.stage === 2 && (
                  <div className="space-y-3">
                    <h4 className="text-[10px] font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-widest">
                      📡 실시간 웹 교차 수집 출처 ({selectedItem.sources?.length || 0}건)
                    </h4>
                    <div className="space-y-2.5 max-h-[320px] overflow-y-auto pr-1">
                      {selectedItem.sources && selectedItem.sources.length > 0 ? (
                        selectedItem.sources.map((src, index) => (
                          <div 
                            key={index}
                            className="bg-zinc-50 dark:bg-[#15151a] border border-zinc-200/60 dark:border-zinc-800 rounded-xl p-3.5 text-xs space-y-1.5 hover:border-zinc-300 dark:hover:border-zinc-700 transition-colors shadow-sm"
                          >
                            <div className="flex justify-between items-start gap-2">
                              <h5 className="font-bold text-zinc-950 dark:text-zinc-100 line-clamp-1 flex-1 leading-tight">{src.title}</h5>
                              <a 
                                href={src.link} 
                                target="_blank" 
                                rel="noreferrer"
                                className="text-blue-500 hover:text-blue-600 shrink-0"
                              >
                                <ExternalLink size={12} />
                              </a>
                            </div>
                            <p className="text-[11px] text-zinc-400 leading-relaxed line-clamp-2">{src.description}</p>
                            <div className="text-[9px] text-zinc-400/80 font-mono text-right">{src.pub_date}</div>
                          </div>
                        ))
                      ) : (
                        <p className="text-xs text-zinc-400 text-center py-6 border border-dashed border-zinc-200 dark:border-zinc-800 rounded-xl">
                          실시간 수집된 관련 교차 출처가 존재하지 않습니다.
                        </p>
                      )}
                    </div>
                  </div>
                )}

              </div>

              {/* Panel Delete Actions */}
              <div className="border-t border-zinc-200 dark:border-zinc-800/80 pt-4 mt-6 flex gap-2">
                <button 
                  onClick={(e) => handleDelete(selectedItem.id, e)}
                  className="flex-1 border border-rose-200 dark:border-rose-900/30 hover:bg-rose-50 dark:hover:bg-rose-950/20 text-rose-600 dark:text-rose-400 py-2.5 rounded-xl font-bold text-xs transition-colors flex items-center justify-center gap-1.5"
                >
                  <Trash2 size={14} /> 레포트 삭제
                </button>
              </div>

            </div>
          )}

        </div>

      </div>

    </div>
  );
}
