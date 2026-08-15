import React, { useState, useEffect, useMemo } from "react";
import { Shield, TrendingUp, Moon, Sun, ArrowRight } from "lucide-react";

// 행별 페이드 감쇠 (피그마 디자인의 스택 페이드 재현)
const ROW_OPACITY = [1, 0.72, 0.55, 0.4, 0.28];
const TICKER_INTERVAL_MS = 4000;

// 팩트체크 판정 배지 — 색상은 대시보드 판정 배지와 통일(진짜=초록/가짜=빨강/의심=주황)
const VERDICT_BADGE = {
  REAL: {
    label: "진짜뉴스",
    cls: "bg-success-50 text-success-700 border-success-500/25 dark:bg-success-950/40 dark:text-success-400",
  },
  FAKE: {
    label: "가짜뉴스",
    cls: "bg-error-50 text-error-600 border-error-500/25 dark:bg-error-950/40 dark:text-error-400",
  },
  SUSPICIOUS: {
    label: "의심",
    cls: "bg-warning-50 text-warning-700 border-warning-500/25 dark:bg-warning-950/40 dark:text-warning-400",
  },
};
const verdictBadge = (verdict) => VERDICT_BADGE[verdict] || VERDICT_BADGE.SUSPICIOUS;

export default function Landing({ darkMode, setDarkMode, history, loading, onSubmit, onOpenDashboard }) {
  const [url, setUrl] = useState("");
  const [offset, setOffset] = useState(0);
  const [paused, setPaused] = useState(false);

  // URL별 검증 횟수 상위 5건 (동률이면 최신순)
  const topArticles = useMemo(() => {
    if (!Array.isArray(history)) return [];
    const grouped = new Map();
    for (const item of history) {
      if (!item || !item.url) continue;
      const entry = grouped.get(item.url);
      if (entry) {
        entry.count += 1;
        const currentCreatedAt = new Date(item.created_at || 0).getTime();
        const entryCreatedAt = new Date(entry.item.created_at || 0).getTime();
        if (currentCreatedAt > entryCreatedAt) {
          entry.item = item;
        }
      } else {
        grouped.set(item.url, { count: 1, item });
      }
    }
    return [...grouped.values()]
      .sort(
        (a, b) =>
          b.count - a.count ||
          new Date(b.item.created_at || 0).getTime() - new Date(a.item.created_at || 0).getTime()
      )
      .slice(0, 5)
      .map((e) => ({ ...e.item, count: e.count }));
  }, [history]);

  // 시간 간격을 두고 다음 기사로 자동 전환 (hover·백그라운드 탭에서는 일시정지)
  useEffect(() => {
    if (topArticles.length < 2) return;
    const id = setInterval(() => {
      if (!paused && !document.hidden) {
        setOffset((o) => (o + 1) % topArticles.length);
      }
    }, TICKER_INTERVAL_MS);
    return () => clearInterval(id);
  }, [topArticles.length, paused]);

  const rotated = topArticles.map((_, i) => {
    const srcIdx = (offset + i) % topArticles.length;
    return { ...topArticles[srcIdx], rank: srcIdx + 1 };
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!url.trim()) return;
    onSubmit(url);
  };

  return (
    <div className="min-h-screen bg-neutral-50 dark:bg-neutral-950 text-neutral-900 dark:text-neutral-100 font-sans flex flex-col transition-colors duration-200">
      {/* Top bar: 로고 + 보조 링크/테마 토글 */}
      <header className="float-in flex items-center justify-between px-6 md:px-10 py-6">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-brand-500 dark:bg-brand-400 rounded-lg text-white shadow-md shadow-brand-500/20">
            <Shield size={24} />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-brand-500 via-brand-400 to-secondary-600 dark:from-brand-300 dark:via-brand-200 dark:to-secondary-400">
              Fake News Defender
            </h1>
            <p className="text-[10px] text-neutral-400 font-semibold tracking-wider uppercase mt-0.5">
              Hybrid Fact-Checker
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={onOpenDashboard}
            className="flex items-center gap-1 text-xs font-bold text-neutral-500 dark:text-neutral-400 hover:text-brand-600 dark:hover:text-brand-300 px-3 py-2 rounded-md hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
          >
            대시보드 보기 <ArrowRight size={13} />
          </button>
          <button
            onClick={() => setDarkMode(!darkMode)}
            className="p-2 border border-neutral-200 dark:border-neutral-800 rounded-md hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors text-neutral-500 dark:text-neutral-400"
          >
            {darkMode ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
      </header>

      {/* 중앙 히어로 */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 pb-16 -mt-8">
        {/* 아이브로: Figma = SUIT Regular, 네이비→그린 그라디언트 (다크 모드는 시인성 위해 한 단계 밝게) */}
        <p
          className="float-in text-xl md:text-[26px] font-normal bg-clip-text text-transparent bg-gradient-to-r from-brand-300 to-secondary-600 dark:from-brand-200 dark:to-secondary-400"
          style={{ animationDelay: "60ms" }}
        >
          그 기사.. 팩트일까요?
        </p>
        {/* 헤드라인: Figma = SUIT Heavy, 네이비(0%)→블루(71%) 그라디언트.
            자간은 대형 헤드라인에 맞춰 더 조이고(-0.03em), 다크 모드는 시작 네이비가 묻히지 않도록 밝은 블루로 승급 */}
        <h2
          className="float-in mt-1 text-4xl md:text-5xl font-black tracking-[-0.03em] text-center leading-tight bg-clip-text text-transparent bg-gradient-to-r from-brand-500 from-0% to-info-600 to-[71%] dark:from-brand-300 dark:to-info-400"
          style={{ animationDelay: "140ms" }}
        >
          AI에게 팩트를 체크해보세요.
        </h2>

        {/* 알약형 검색 입력 + 내장 검증하기 버튼 */}
        <form
          onSubmit={handleSubmit}
          className="float-in mt-8 w-full max-w-2xl relative"
          style={{ animationDelay: "220ms" }}
        >
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="검증하려는 기사, 인스타그램·X(트위터) 게시물 링크를 입력해 주세요."
            required
            disabled={loading}
            className="w-full h-14 bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-full pl-6 pr-30 text-sm shadow-md dark:shadow-[0_0_28px_rgba(255,255,255,0.10)] focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 dark:focus:ring-brand-400/30 dark:focus:border-brand-400 transition-all text-neutral-950 dark:text-neutral-100 disabled:opacity-60 disabled:cursor-not-allowed"
          />
          <button
            type="submit"
            disabled={loading}
            className="absolute right-2 top-1/2 -translate-y-1/2 h-10 bg-brand-500 hover:bg-brand-600 active:bg-brand-700 text-white text-sm font-bold px-7 rounded-full transition-colors shadow-sm shadow-brand-500/10 dark:shadow-[0_0_16px_rgba(255,255,255,0.12)] disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? "검증 중..." : "검증하기"}
          </button>
        </form>

        {/* 실시간 가장 많이 검증된 기사 (Top 5) 티커 */}
        <section
          className="float-in mt-8 w-full max-w-xl"
          style={{ animationDelay: "300ms" }}
        >
          <p className="flex items-center justify-center gap-1.5 text-xs font-bold text-neutral-700 dark:text-neutral-300">
            <TrendingUp size={14} className="text-info-600 dark:text-info-400" />
            실시간 가장 많이 검증된 기사 (Top 5)
          </p>

          <div
            onMouseEnter={() => setPaused(true)}
            onMouseLeave={() => setPaused(false)}
            className="mt-4 bg-white dark:bg-neutral-900 border border-neutral-100 dark:border-neutral-800 rounded-lg shadow-md dark:shadow-[0_0_32px_rgba(255,255,255,0.08)] px-6 py-5 overflow-hidden"
          >
            {topArticles.length === 0 ? (
              <p className="text-xs text-neutral-400 text-center py-4 font-medium">
                아직 검증된 기사가 없습니다. 첫 번째 기사를 검증해 보세요!
              </p>
            ) : (
              <ul key={offset} className="space-y-3 ticker-in">
                {rotated.map((item, idx) => {
                  const badge = verdictBadge(item.verdict);
                  return (
                    <li
                      key={`${item.rank}-${item.url}`}
                      style={{ opacity: ROW_OPACITY[idx] ?? 0.28 }}
                    >
                      {/* 행 전체가 클릭 영역: [순위] [제목……] [팩트체크 배지] */}
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        title={item.title}
                        className="flex items-center gap-3 w-full group"
                      >
                        <span
                          className={`shrink-0 font-bold ${idx === 0
                              ? "text-sm text-info-600 dark:text-info-400"
                              : "text-xs text-info-500 dark:text-info-400"
                            }`}
                        >
                          {item.rank}
                        </span>
                        <span
                          className={`flex-1 min-w-0 truncate text-left group-hover:underline ${idx === 0
                              ? "text-sm font-bold text-neutral-900 dark:text-neutral-100"
                              : "text-xs font-medium text-neutral-700 dark:text-neutral-300"
                            }`}
                        >
                          {item.title}
                        </span>
                        <span
                          className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold ${badge.cls}`}
                        >
                          {badge.label}
                        </span>
                      </a>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
