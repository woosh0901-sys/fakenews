import React from "react";
import { Search, Loader2, CheckCircle } from "lucide-react";

export default function SearchSection({
  urlInput,
  setUrlInput,
  loading,
  activeStep,
  loaderSteps,
  onCheck,
  onQuickFill
}) {
  const sampleUrls = [
    { label: "🔥 화물차 화재 (진짜 뉴스)", url: "https://www.1gan.co.kr/news/articleView.html?idxno=379965" },
    { label: "⚽ 음바페 경기 (정상 보도)", url: "https://m.sports.naver.com/fifaworldcup2026/article/025/0003535350" },
    { label: "📰 네이버 뉴스 검증", url: "https://n.news.naver.com/mnews/article/001/0014782046" }
  ];

  return (
    <section className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800/80 rounded-lg p-5 shadow-sm relative overflow-hidden">
      <div className="absolute top-0 left-0 w-full h-[3px] bg-gradient-to-r from-brand-500 via-brand-400 to-secondary-500"></div>

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-bold tracking-tight text-neutral-950 dark:text-neutral-50">인공지능 교차 검증</h2>
          <span className="text-[11px] text-neutral-400 dark:text-neutral-500 font-medium">
            실시간 웹 교차 검색 및 Gemini AI 정밀 대조로 판정합니다.
          </span>
        </div>
      </div>

      <form onSubmit={onCheck} className="flex gap-2.5 mt-3.5">
        <div className="relative flex-1">
          <input 
            type="url" 
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            placeholder="검증하려는 기사, 인스타그램·X(트위터) 게시물 링크(https://...)를 입력해 주세요."
            required
            disabled={loading}
            className="w-full bg-neutral-50 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 rounded-lg pl-11 pr-4 py-3.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 dark:focus:ring-brand-400/30 dark:focus:border-brand-400 transition-all text-neutral-950 dark:text-neutral-100 shadow-inner"
          />
          <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-neutral-400" />
        </div>
        <button 
          type="submit"
          disabled={loading}
          className="bg-brand-500 hover:bg-brand-600 active:bg-brand-700 text-white rounded-md px-7 py-3.5 font-bold transition-all shadow-sm shadow-brand-500/10 disabled:opacity-40 disabled:cursor-not-allowed text-sm shrink-0 flex items-center justify-center gap-1.5"
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

      {/* Quick Test Samples Bar */}
      <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-neutral-100 dark:border-neutral-800/60">
        <span className="text-[11px] font-bold text-neutral-400 dark:text-neutral-500 shrink-0">
          💡 빠른 시연용 예시:
        </span>
        <div className="flex flex-wrap gap-1.5">
          {sampleUrls.map((sample, idx) => (
            <button
              key={idx}
              type="button"
              disabled={loading}
              onClick={() => onQuickFill && onQuickFill(sample.url)}
              className="text-[11px] bg-neutral-50 dark:bg-neutral-800 border border-neutral-200/80 dark:border-neutral-700/60 hover:border-brand-500/50 dark:hover:border-brand-400/50 text-neutral-600 dark:text-neutral-300 hover:text-brand-600 dark:hover:text-brand-300 font-medium px-2.5 py-1 rounded-md transition-colors"
            >
              {sample.label}
            </button>
          ))}
        </div>
      </div>

      {/* Dynamic Loading Timeline/Stepper */}
      {loading && (
        <div className="mt-6 pt-6 border-t border-neutral-100 dark:border-neutral-800/80 space-y-4">
          <div className="flex items-center justify-between text-xs font-bold text-neutral-400 uppercase tracking-widest">
            <span>RAG-LLM 탐지 파이프라인 분석 단계</span>
            <span className="text-brand-500 dark:text-brand-300 flex items-center gap-1.5 animate-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-brand-500 dark:bg-brand-300"></span>
              실시간 분석 중
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {loaderSteps.map((step, idx) => {
              const isCompleted = activeStep > idx + 1;
              const isActive = activeStep === idx + 1;
              return (
                <div 
                  key={idx}
                  className={`border rounded-lg p-3.5 transition-all duration-300 flex flex-col justify-between ${
                    isActive 
                      ? "bg-brand-50/60 dark:bg-brand-900/30 border-brand-500/50 dark:border-brand-300/30 shadow-[0_0_15px_rgba(30,58,95,0.08)]" 
                      : isCompleted
                        ? "bg-neutral-50/50 dark:bg-neutral-900/30 border-success-500/30 dark:border-success-500/20"
                        : "bg-neutral-50/30 dark:bg-neutral-900/10 border-neutral-200 dark:border-neutral-800/60 opacity-60"
                  }`}
                >
                  <div className="flex justify-between items-center">
                    <span className={`text-[10px] font-bold uppercase tracking-wider ${
                      isActive ? "text-brand-600 dark:text-brand-300" : isCompleted ? "text-success-700 dark:text-success-400" : "text-neutral-400"
                    }`}>
                      {step.label}
                    </span>
                    {isCompleted && (
                      <CheckCircle size={14} className="text-success-500 shrink-0" />
                    )}
                    {isActive && (
                      <Loader2 size={14} className="animate-spin text-brand-500 dark:text-brand-300 shrink-0" />
                    )}
                  </div>
                  <p className="text-xs text-neutral-500 dark:text-neutral-400 font-medium mt-1">{step.desc}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}
