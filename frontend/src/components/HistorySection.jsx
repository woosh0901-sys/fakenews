import React from "react";
import { History, Trash2 } from "lucide-react";

export default function HistorySection({
  history,
  selectedItem,
  onSelectItem,
  onDeleteItem,
  getVerdictBadge
}) {
  return (
    <section className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800/80 rounded-lg shadow-sm overflow-hidden">
      <div className="p-5 border-b border-neutral-200 dark:border-neutral-800/60 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <History size={18} className="text-neutral-400" />
          <h2 className="text-md font-bold tracking-tight text-neutral-950 dark:text-neutral-50">검증 히스토리</h2>
        </div>
        <span className="text-xs font-mono bg-neutral-100 dark:bg-neutral-800 text-neutral-500 dark:text-neutral-400 px-2 py-0.5 rounded-md font-bold">
          기록 수: {history.length}건
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm whitespace-nowrap">
          <thead className="bg-neutral-50 dark:bg-neutral-900/20 text-neutral-500 dark:text-neutral-400 border-b border-neutral-200 dark:border-neutral-800">
            <tr>
              <th className="p-4 font-bold text-xs uppercase tracking-wider">판정 결과</th>
              <th className="p-4 font-bold text-xs uppercase tracking-wider">기사 제목 / 주소</th>
              <th className="p-4 font-bold text-xs uppercase tracking-wider text-center">모순 점수</th>
              <th className="p-4 font-bold text-xs uppercase tracking-wider text-right">삭제</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100 dark:divide-neutral-800/60">
            {history.length === 0 ? (
              <tr>
                <td colSpan="4" className="p-12 text-center text-neutral-500 dark:text-neutral-400 font-medium">
                  검증 기록이 존재하지 않습니다. 뉴스 링크를 입력하여 신뢰도를 판정해 보세요.
                </td>
              </tr>
            ) : (
              history.map((item) => {
                const isSelected = selectedItem?.id === item.id;
                const score = item.contradiction_score || 0;
                return (
                  <tr 
                    key={item.id || item.url}
                    onClick={() => onSelectItem(item)}
                    className={`hover:bg-neutral-50/50 dark:hover:bg-neutral-900/20 cursor-pointer transition-colors ${
                      isSelected ? "bg-brand-50/60 dark:bg-brand-900/25 hover:bg-brand-50/80 dark:hover:bg-brand-900/35" : ""
                    }`}
                  >
                    <td className="p-4">{getVerdictBadge(item.verdict)}</td>
                    <td className="p-4 max-w-sm md:max-w-md truncate">
                      <span className="block text-neutral-950 dark:text-neutral-50 font-bold leading-tight truncate">
                        {item.title}
                      </span>
                      <span className="text-xs text-neutral-400 font-medium truncate block mt-0.5 max-w-xs md:max-w-md">
                        {item.url}
                      </span>
                    </td>
                    <td className="p-4 text-center font-mono font-bold text-xs">
                      <div className="flex items-center justify-center gap-1.5">
                        <span className={score > 0.6 ? "text-error-500" : score > 0.2 ? "text-warning-500" : "text-success-500"}>
                          {score.toFixed(2)}
                        </span>
                      </div>
                    </td>
                    <td className="p-4 text-right">
                      <button 
                        onClick={(e) => onDeleteItem(item.id, e)}
                        className="text-neutral-400 hover:text-error-500 p-1.5 rounded-md hover:bg-neutral-100 dark:hover:bg-neutral-800/80 transition-colors"
                        title="기록 삭제"
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
  );
}
