import React from "react";
import { TrendingUp, AlertTriangle } from "lucide-react";

export default function RankingsSection({ rankings, history, onSelectItem }) {
  return (
    <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
      
      {/* Most Checked Rankings */}
      <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800/80 rounded-lg p-5 shadow-sm space-y-4">
        <h3 className="text-sm font-bold text-neutral-900 dark:text-neutral-100 flex items-center gap-2">
          <TrendingUp size={16} className="text-info-500 dark:text-info-400" />
          실시간 가장 많이 검증된 기사 (Top 5)
        </h3>
        <div className="space-y-2">
          {(rankings.most_checked || []).length === 0 ? (
            <p className="text-xs text-neutral-400 py-4 text-center">검증 통계가 없습니다.</p>
          ) : (
            (rankings.most_checked || []).map((item, idx) => (
              <div
                key={idx}
                onClick={() => {
                  const matched = history.find(h => h.url === item.url);
                  if (matched) onSelectItem(matched);
                }}
                className="flex items-center justify-between gap-3 text-xs p-3 bg-neutral-50 dark:bg-neutral-800/50 border border-neutral-200/60 dark:border-neutral-800 rounded-lg hover:border-info-500/40 dark:hover:border-info-400/40 cursor-pointer transition-colors"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="font-mono font-bold text-info-600 dark:text-info-400 bg-info-50 dark:bg-info-950/40 px-2 py-0.5 rounded text-[10px] shrink-0">
                    {idx + 1}
                  </span>
                  <span className="font-bold text-neutral-900 dark:text-neutral-100 truncate flex-1 block leading-tight">
                    {item.title}
                  </span>
                </div>
                <span className="text-[10px] text-neutral-500 dark:text-neutral-400 shrink-0 font-bold bg-neutral-100 dark:bg-neutral-800 px-2 py-0.5 rounded-full">
                  {item.count}회
                </span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Top Fakes Rankings */}
      <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800/80 rounded-lg p-5 shadow-sm space-y-4">
        <h3 className="text-sm font-bold text-neutral-900 dark:text-neutral-100 flex items-center gap-2">
          <AlertTriangle size={16} className="text-error-500 dark:text-error-400" />
          실시간 모순율이 가장 높은 거짓 기사 (Top 5)
        </h3>
        <div className="space-y-2">
          {(rankings.top_fakes || []).length === 0 ? (
            <p className="text-xs text-neutral-400 py-4 text-center">검출된 거짓 기사가 없습니다.</p>
          ) : (
            (rankings.top_fakes || []).map((item, idx) => (
              <div
                key={idx}
                onClick={() => {
                  const matched = history.find(h => h.url === item.url);
                  if (matched) onSelectItem(matched);
                }}
                className="flex items-center justify-between gap-3 text-xs p-3 bg-error-50/40 dark:bg-error-950/15 border border-error-500/15 dark:border-error-500/15 rounded-lg hover:border-error-500/40 dark:hover:border-error-400/40 cursor-pointer transition-colors"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="font-mono font-bold text-error-600 dark:text-error-400 bg-error-50 dark:bg-error-950/40 px-2 py-0.5 rounded text-[10px] shrink-0">
                    {idx + 1}
                  </span>
                  <span className="font-bold text-neutral-900 dark:text-neutral-100 truncate flex-1 block leading-tight">
                    {item.title}
                  </span>
                </div>
                <span className="text-[10px] text-error-600 dark:text-error-400 shrink-0 font-bold bg-error-50 dark:bg-error-950/40 px-2 py-0.5 rounded-full">
                  모순율 {((item.contradiction_score || 0) * 100).toFixed(0)}%
                </span>
              </div>
            ))
          )}
        </div>
      </div>

    </section>
  );
}
