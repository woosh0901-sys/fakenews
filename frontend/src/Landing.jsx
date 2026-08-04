import React, { useState, useEffect, useMemo, useRef } from "react";
import { ArrowRight, Loader2, CheckCircle } from "lucide-react";
import { verdictTone } from "./verdict";

// 행별 페이드 감쇠 (아래로 갈수록 흐려지는 스택)
const ROW_OPACITY = [1, 0.72, 0.55, 0.4, 0.28];
const TICKER_INTERVAL_MS = 4000;

export default function Landing({
  history, loading, onSubmit, onOpenDashboard,
  analyzing = false, analysisDone = false, preview = null,
}) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [offset, setOffset] = useState(0);
  const [paused, setPaused] = useState(false);

  // 분석 로딩 화면에 흘려보낼 기사 본문 문단
  const paragraphs = useMemo(() => {
    const raw = (preview?.content || "").trim();
    if (!raw) return [];
    const byLine = raw.split(/\n+/).map((s) => s.trim()).filter((s) => s.length > 10);
    if (byLine.length > 1) return byLine.slice(0, 24);
    // 한 덩어리로 온 경우 문장 두 개씩 묶어 문단화
    const sentences = raw.split(/(?<=[.!?。])\s+/).map((s) => s.trim()).filter(Boolean);
    const out = [];
    for (let i = 0; i < sentences.length; i += 2) out.push(sentences.slice(i, i + 2).join(" "));
    return out.slice(0, 24);
  }, [preview]);

  // 기사 본문을 티커처럼 한 문단씩 끊어 올린다
  const scanRef = useRef(null);
  const [scanStep, setScanStep] = useState(0);
  const [scanY, setScanY] = useState(0);

  useEffect(() => {
    if (!analyzing || analysisDone || paragraphs.length === 0) return;
    const id = setInterval(() => setScanStep((s) => s + 1), 1700);
    return () => clearInterval(id);
  }, [analyzing, analysisDone, paragraphs.length]);

  // 문단 높이가 제각각이므로 실제 offsetTop을 재서 정확히 한 문단씩 정렬
  useEffect(() => {
    const el = scanRef.current;
    if (!el || paragraphs.length === 0) return;
    const kids = el.children;
    const idx = scanStep % paragraphs.length;
    if (kids.length > idx) {
      setScanY(kids[idx].offsetTop - kids[0].offsetTop);
    }
  }, [scanStep, paragraphs.length]);

  // 되감기(0번으로 복귀) 프레임에서는 전환을 끊어 역주행이 보이지 않게 한다
  const isRewind = paragraphs.length > 0 && scanStep % paragraphs.length === 0 && scanStep !== 0;

  // 티커 → 분석 블록 전환: 티커를 먼저 부드럽게 내보낸 뒤 분석 블록을 띄운다
  const [tickerVisible, setTickerVisible] = useState(true);
  useEffect(() => {
    if (!analyzing) {
      setTickerVisible(true);
      return;
    }
    const t = setTimeout(() => setTickerVisible(false), 280);
    return () => clearTimeout(t);
  }, [analyzing]);

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
    const trimmed = url.trim();
    if (!trimmed) return;

    // 링크 전용 — 도메인 형태가 아니면 제출하지 않고 인라인으로 알린다
    const isUrl =
      trimmed.startsWith("http://") ||
      trimmed.startsWith("https://") ||
      (trimmed.split("/")[0].includes(".") && !trimmed.includes(" "));

    if (!isUrl) {
      setError("검증할 기사 링크(https://...)를 붙여 넣어 주세요.");
      return;
    }

    setError("");
    onSubmit(trimmed);
  };

  const kicker = "text-[11px] font-bold uppercase tracking-[0.18em]";

  return (
    <div className="min-h-screen bg-neutral-0 text-neutral-900 font-sans flex flex-col">
      {/* 마스트헤드 */}
      <header className="float-in border-b border-neutral-900">
        <div className="mx-auto w-full max-w-[1100px] px-6 md:px-10 h-14 flex items-center justify-between gap-4">
          <span className="text-[17px] font-black uppercase tracking-[-0.01em] text-brand-500">
            Fake News Defender
          </span>
          <button
            onClick={onOpenDashboard}
            className={`inline-flex items-center gap-1.5 ${kicker} text-neutral-400 hover:text-neutral-900 transition-colors`}
          >
            대시보드 <ArrowRight size={12} />
          </button>
        </div>
      </header>

      {/* 중앙 히어로 */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 pb-20 -mt-6">
        <p className={`float-in ${kicker} text-neutral-500`} style={{ animationDelay: "60ms" }}>
          그 기사, 팩트일까요?
        </p>

        <h1
          className="float-in mt-4 text-[34px] md:text-[56px] font-black leading-[1.05] tracking-[-0.04em] text-center text-balance text-neutral-900"
          style={{ animationDelay: "140ms" }}
        >
          AI에게 팩트를 체크해보세요.
        </h1>

        {/* 링크 입력 */}
        <form
          onSubmit={handleSubmit}
          className="float-in mt-10 w-full max-w-2xl"
          style={{ animationDelay: "220ms" }}
          noValidate
        >
          <div className="flex items-end gap-3 md:gap-5">
            <input
              type="text"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                if (error) setError("");
              }}
              placeholder="검증할 뉴스·인스타그램·X 링크를 붙여 넣으세요"
              disabled={loading}
              aria-invalid={!!error}
              className={`flex-1 min-w-0 bg-transparent border-0 border-b-2 px-0 py-3 text-base md:text-lg text-neutral-900 placeholder:text-neutral-400 focus:outline-none transition-colors disabled:opacity-40 ${
                error ? "border-error-500 focus:border-error-500" : "border-neutral-900 focus:border-brand-500"
              }`}
            />
            <button
              type="submit"
              disabled={loading}
              className="shrink-0 bg-neutral-900 text-white px-6 md:px-8 py-3 text-[12px] font-bold uppercase tracking-[0.14em] hover:bg-brand-500 active:bg-brand-600 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            >
              {loading ? "검증 중" : "검증"}
            </button>
          </div>
          {error && <p className="mt-2 text-[11px] text-error-600">{error}</p>}
        </form>

        {/* 분석 중: 상태줄 + 기사 본문 스캔 */}
        {analyzing && !tickerVisible ? (
          <section className="float-in mt-10 w-full max-w-2xl" style={{ animationDelay: "40ms" }}>
            <p className="flex items-center justify-center gap-2 text-[15px] md:text-base font-bold text-neutral-900 text-center">
              {analysisDone ? (
                <>
                  <CheckCircle size={18} className="text-success-600 shrink-0" />
                  분석이 완료되었어요
                </>
              ) : (
                <>
                  <span>
                    {preview?.source ? `${preview.source} 기사를 분석중이에요` : "기사를 분석중이에요"}
                  </span>
                  <Loader2 size={18} className="spin text-neutral-900 shrink-0" />
                </>
              )}
            </p>

            {/* 기사 본문 — 한 문단씩 올라가며 위아래로 사라짐 */}
            <div className="mt-6 h-[300px] overflow-hidden article-fade" aria-hidden="true">
              {paragraphs.length === 0 ? (
                <div className="space-y-3 animate-pulse">
                  {[88, 76, 92, 68, 84].map((w, i) => (
                    <div key={i} className="h-3 bg-neutral-200 mx-auto" style={{ width: `${w}%` }} />
                  ))}
                </div>
              ) : (
                <div
                  ref={scanRef}
                  className={`article-scan space-y-3.5 ${isRewind ? "no-transition" : ""}`}
                  style={{ transform: `translateY(-${scanY}px)` }}
                >
                  {[...paragraphs, ...paragraphs].map((p, i) => {
                    // 지금 '분석 중'인 문단 하나만 진하게
                    const active = i === (scanStep % paragraphs.length) + 1;
                    return (
                      <p
                        key={i}
                        className={`text-xs leading-relaxed text-center px-4 transition-colors duration-500 ${
                          active ? "text-neutral-900" : "text-neutral-400"
                        }`}
                      >
                        {p}
                      </p>
                    );
                  })}
                </div>
              )}
            </div>
          </section>
        ) : (
          /* 실시간 가장 많이 검증된 기사 (Top 5) */
          <div
            className={`w-full flex justify-center transition-all duration-300 ease-out ${
              analyzing ? "opacity-0 -translate-y-2" : "opacity-100"
            }`}
          >
            <section className="float-in mt-14 w-full max-w-xl" style={{ animationDelay: "300ms" }}>
              <h2 className={`${kicker} text-neutral-500 text-center`}>실시간 가장 많이 검증된 기사</h2>

              <div
                onMouseEnter={() => setPaused(true)}
                onMouseLeave={() => setPaused(false)}
                className="mt-4 border-t border-neutral-900 overflow-hidden"
              >
                {topArticles.length === 0 ? (
                  <p className="text-[12px] text-neutral-400 text-center py-6">
                    아직 검증된 기사가 없습니다. 첫 기사를 검증해 보세요.
                  </p>
                ) : (
                  <ul key={offset} className="ticker-in divide-y divide-neutral-200">
                    {rotated.map((item, idx) => {
                      const t = verdictTone(item.verdict);
                      return (
                        <li key={`${item.rank}-${item.url}`} style={{ opacity: ROW_OPACITY[idx] ?? 0.28 }}>
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noreferrer"
                            title={item.title}
                            className="flex items-center gap-3 w-full py-3 group"
                          >
                            <span className="w-4 shrink-0 text-[12px] font-black tabular-nums text-neutral-300">
                              {item.rank}
                            </span>
                            <span
                              className={`flex-1 min-w-0 truncate text-left text-neutral-900 group-hover:underline underline-offset-[3px] ${
                                idx === 0 ? "text-[14px] font-bold" : "text-[13px]"
                              }`}
                            >
                              {item.title}
                            </span>
                            <span
                              className={`shrink-0 inline-flex items-center gap-2 text-[11px] font-bold tracking-[0.12em] ${t.text}`}
                            >
                              <span className={`h-[3px] w-4 shrink-0 ${t.bar}`} />
                              {t.short}
                            </span>
                          </a>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
