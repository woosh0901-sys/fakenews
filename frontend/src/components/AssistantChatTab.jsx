import React from "react";
import { MessageSquare, Globe, Loader2, Send } from "lucide-react";

export default function AssistantChatTab({
  generalChatHistory,
  setGeneralChatHistory,
  generalChatInput,
  setGeneralChatInput,
  loadingGeneralChat,
  onGeneralChatSubmit
}) {
  const suggestionQueries = [
    "성수대교 진입로 9cm 단차 발생 사실인가요?",
    "박세리 아버지가 재단 인장 위조로 고소당한 일 진짜인가요?",
    "벨기에 전투기 우크라이나 지원 출격 여부 팩트체크"
  ];

  const handleReset = () => {
    setGeneralChatHistory([
      {
        query: null,
        answer: "안녕하세요! 실시간 웹 검색과 RAG-LLM 기반의 AI 팩트체커 어시스턴트입니다. 궁금한 소문, 뉴스, 루머에 대해 질문하시면 실시간으로 관련 사실을 추적하고 검증 결과를 알려드립니다. (예: '성수대교 단차 9cm 사실인가요?')",
        sources: [],
        isSystem: true
      }
    ]);
  };

  return (
    <div className="flex-1 flex flex-col h-full p-6 space-y-4 max-w-full overflow-hidden">
      <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800/80 rounded-2xl p-6 shadow-sm flex flex-col h-[calc(100vh-140px)] relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-[3px] bg-gradient-to-r from-brand-500 via-brand-400 to-secondary-500"></div>
        
        {/* Chat Panel Header */}
        <div className="border-b border-neutral-100 dark:border-neutral-800 pb-4 mb-4 flex justify-between items-center shrink-0">
          <div>
            <h2 className="text-lg font-bold tracking-tight text-neutral-950 dark:text-neutral-50 flex items-center gap-2">
              <MessageSquare className="text-brand-500" size={20} />
              AI 팩트체크 어시스턴트
            </h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
              자유롭게 소문이나 루머를 질문하세요. 실시간 웹 보도를 수집하여 팩트를 분석해 드립니다.
            </p>
          </div>
          <button 
            onClick={handleReset}
            className="text-xs text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 flex items-center gap-1 border border-neutral-200 dark:border-neutral-800 rounded-lg px-2.5 py-1"
          >
            대화 초기화
          </button>
        </div>

        {/* Chat Message Logs Area */}
        <div className="flex-1 overflow-y-auto space-y-4 pr-1 mb-4">
          {generalChatHistory.map((chat, idx) => (
            <div key={idx} className="space-y-2">
              {/* User Query */}
              {chat.query && (
                <div className="flex justify-end">
                  <div className="bg-brand-500 text-white px-4 py-2.5 rounded-2xl rounded-tr-none text-sm font-bold shadow-sm max-w-[75%]">
                    {chat.query}
                  </div>
                </div>
              )}

              {/* AI Answer */}
              <div className="flex justify-start">
                <div className="bg-neutral-50 dark:bg-neutral-850 border border-neutral-200/50 dark:border-neutral-800 text-neutral-900 dark:text-neutral-100 px-4 py-3 rounded-2xl rounded-tl-none text-sm font-medium shadow-sm max-w-[85%] space-y-3 leading-relaxed">
                  {chat.loading ? (
                    <span className="flex items-center gap-2 text-neutral-500 dark:text-neutral-400 font-bold py-1">
                      <Loader2 size={16} className="animate-spin" /> 실시간 보도 검색 및 RAG AI 분석 진행 중...
                    </span>
                  ) : (
                    <>
                      <div className="whitespace-pre-wrap text-neutral-800 dark:text-neutral-200">
                        {chat.answer}
                      </div>

                      {/* Search Sources for this reply */}
                      {chat.sources && chat.sources.length > 0 && (
                        <div className="pt-3 border-t border-neutral-200/50 dark:border-neutral-800 space-y-2">
                          <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest flex items-center gap-1">
                            <Globe size={11} /> 교차 검증 참고 출처 ({chat.sources.length}건)
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {chat.sources.map((src, sIdx) => (
                              <a
                                key={sIdx}
                                href={src.link}
                                target="_blank"
                                rel="noreferrer"
                                className="text-[10px] bg-neutral-100 dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700/60 rounded-lg px-2.5 py-1 text-neutral-600 dark:text-neutral-300 hover:text-brand-500 dark:hover:text-brand-400 font-bold truncate max-w-[200px]"
                                title={src.description}
                              >
                                {src.title}
                              </a>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Suggestions Cards */}
        {generalChatHistory.length === 1 && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 mb-4 shrink-0">
            {suggestionQueries.map((sug, sIdx) => (
              <button
                key={sIdx}
                onClick={(e) => onGeneralChatSubmit(e, sug)}
                className="text-left text-xs bg-neutral-50/50 dark:bg-neutral-900/30 border border-neutral-200 dark:border-neutral-800/80 hover:border-brand-500/60 dark:hover:border-brand-400/40 rounded-xl p-3.5 text-neutral-600 dark:text-neutral-400 hover:text-brand-600 dark:hover:text-brand-300 transition-all font-semibold active:scale-[0.98]"
              >
                {sug}
              </button>
            ))}
          </div>
        )}

        {/* Chat Input form */}
        <form onSubmit={onGeneralChatSubmit} className="flex gap-2 shrink-0">
          <input
            type="text"
            value={generalChatInput}
            onChange={(e) => setGeneralChatInput(e.target.value)}
            placeholder="소문이나 검증이 필요한 질문을 입력해 주세요..."
            disabled={loadingGeneralChat}
            className="flex-1 bg-neutral-50 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 text-neutral-950 dark:text-neutral-100"
          />
          <button
            type="submit"
            disabled={loadingGeneralChat || !generalChatInput.trim()}
            className="bg-brand-500 hover:bg-brand-600 active:bg-brand-700 text-white rounded-xl px-5 py-3 font-bold transition-all shadow-sm disabled:opacity-40 flex items-center justify-center gap-1.5"
          >
            <Send size={16} />
            <span>질문 전송</span>
          </button>
        </form>
      </div>
    </div>
  );
}
