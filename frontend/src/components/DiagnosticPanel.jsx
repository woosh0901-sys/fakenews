import React from "react";
import { 
  X, 
  Globe, 
  Clock, 
  ExternalLink, 
  Info, 
  Layers, 
  HelpCircle, 
  Loader2, 
  Send, 
  MessageSquare, 
  Trash2, 
  Check, 
  AlertCircle 
} from "lucide-react";

export default function DiagnosticPanel({
  selectedItem,
  onClose,
  onDeleteItem,
  getVerdictBadge,
  // Chat
  chatHistory,
  chatInput,
  setChatInput,
  loadingChat,
  onChatSubmit,
  // Reactions
  reactions,
  userReactions,
  onAddReaction,
  // Comments
  comments,
  commentAuthor,
  setCommentAuthor,
  commentContent,
  setCommentContent,
  userToken,
  onAddComment,
  onDeleteComment
}) {
  if (!selectedItem) return null;

  const score = selectedItem.contradiction_score || 0;
  const scorePercent = (score * 100).toFixed(0);

  return (
    <div className="w-full xl:w-[450px] shrink-0 bg-white dark:bg-neutral-900 border-t xl:border-t-0 xl:border-l border-neutral-200 dark:border-neutral-800 p-6 space-y-6 overflow-y-auto z-20 shadow-lg relative flex flex-col justify-between">
      
      <div className="space-y-6">
        
        {/* Panel Header */}
        <div className="flex justify-between items-start border-b border-neutral-200 dark:border-neutral-800/80 pb-4">
          <div className="space-y-1">
            <p className="text-[10px] font-bold text-neutral-400 dark:text-neutral-500 uppercase tracking-widest">
              정밀 진단 레포트
            </p>
            <div className="flex items-center gap-2">
              {getVerdictBadge(selectedItem.verdict)}
              {selectedItem.id != null && (
                <span className="text-xs bg-neutral-100 dark:bg-neutral-800 text-neutral-500 dark:text-neutral-400 px-2 py-0.5 rounded font-mono font-bold">
                  #{selectedItem.id}
                </span>
              )}
            </div>
          </div>
          <button 
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 p-1.5 hover:bg-neutral-100 dark:hover:bg-neutral-800 rounded-md transition-colors border border-neutral-200 dark:border-neutral-800"
            title="닫기"
          >
            <X size={16} />
          </button>
        </div>

        {/* Article info block */}
        <div className="space-y-2">
          <h3 className="text-md font-bold tracking-tight text-neutral-950 dark:text-neutral-50 leading-snug">
            {selectedItem.title}
          </h3>
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            <a 
              href={selectedItem.url} 
              target="_blank" 
              rel="noreferrer"
              className="flex items-center gap-1.5 text-xs text-brand-600 dark:text-brand-300 hover:underline font-bold"
            >
              <Globe size={12} /> 원문 보도 보기 <ExternalLink size={10} />
            </a>
            {selectedItem.created_at && (
              <span className="text-[11px] text-neutral-400 font-semibold flex items-center gap-1">
                <Clock size={12} /> {new Date(selectedItem.created_at).toLocaleString()}
              </span>
            )}
          </div>
        </div>

        {/* Diagnostic Meters */}
        <div className="grid grid-cols-2 gap-3.5">
          <div className="bg-neutral-50 dark:bg-neutral-800 border border-neutral-200/60 dark:border-neutral-800 rounded-lg p-4 shadow-sm space-y-1">
            <p className="text-[10px] text-neutral-400 dark:text-neutral-500 font-bold uppercase tracking-wider">
              주장 모순율
            </p>
            <div className="flex items-baseline gap-1 pt-1">
              <span className={`text-2xl font-bold font-mono ${
                score > 0.6 ? "text-error-500" : score > 0.2 ? "text-warning-500" : "text-success-500"
              }`}>
                {scorePercent}%
              </span>
            </div>
            {/* Progress Bar */}
            <div className="w-full bg-neutral-200 dark:bg-neutral-800 h-1.5 rounded-full mt-2.5 overflow-hidden">
              <div 
                className={`h-full transition-all duration-500 ${
                  score > 0.6 
                    ? "bg-error-500" 
                    : score > 0.2 
                      ? "bg-warning-500" 
                      : "bg-success-500"
                }`}
                style={{ width: `${score * 100}%` }}
              />
            </div>
          </div>

          <div className="bg-neutral-50 dark:bg-neutral-800 border border-neutral-200/60 dark:border-neutral-800 rounded-lg p-4 shadow-sm space-y-1">
            <p className="text-[10px] text-neutral-400 dark:text-neutral-500 font-bold uppercase tracking-wider">
              검증 방법
            </p>
            <div className="flex items-baseline gap-1 pt-1">
              <span className="text-md font-bold text-neutral-900 dark:text-neutral-100">
                실시간 RAG 기사 대조
              </span>
            </div>
            <span className="text-[9px] text-neutral-400 font-bold block mt-4">
              {selectedItem.sources ? `${selectedItem.sources.length}개 교차 검증 소스` : "실시간 웹 검색 활용"}
            </span>
          </div>
        </div>

        {/* Server-side warning */}
        {selectedItem.warning && (
          <div className="bg-warning-50 dark:bg-warning-950/40 border border-warning-500/40 dark:border-warning-500/30 rounded-lg p-3 text-[11px] text-warning-700 dark:text-warning-400 font-semibold">
            ⚠️ {selectedItem.warning}
          </div>
        )}

        {/* Verdict explanation card */}
        <div className="space-y-2">
          <h4 className="text-[10px] font-bold text-neutral-400 dark:text-neutral-500 uppercase tracking-widest flex items-center gap-1.5">
            <Info size={14} className="text-neutral-400" /> 종합 분석 소견
          </h4>
          <div className="bg-neutral-50 dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-800 rounded-lg p-4 text-xs text-neutral-700 dark:text-neutral-300 leading-relaxed font-semibold">
            {selectedItem.reason}
          </div>
        </div>

        {/* Claims Breakdown (진실/거짓 요소별 분류) */}
        {selectedItem.claims_breakdown && selectedItem.claims_breakdown.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-[10px] font-bold text-neutral-400 dark:text-neutral-500 uppercase tracking-widest flex items-center gap-1.5">
              <Layers size={14} className="text-neutral-400" /> 요소별 세부 검증 (진실/거짓 분류)
            </h4>
            <div className="space-y-2">
              {selectedItem.claims_breakdown.map((item, idx) => {
                const isTrue = item.truth === "진실";
                const isFalse = item.truth === "거짓";
                return (
                  <div
                    key={idx}
                    className="bg-neutral-50 dark:bg-neutral-800 border border-neutral-200/60 dark:border-neutral-800 rounded-lg p-3.5 text-xs space-y-1.5 shadow-sm"
                  >
                    <div className="flex items-center gap-2">
                      {isTrue ? (
                        <span className="flex items-center gap-1 text-[10px] bg-success-50 dark:bg-success-950/40 text-success-700 dark:text-success-400 font-bold border border-success-500/25 px-2 py-0.5 rounded-full shrink-0">
                          <Check size={10} /> {item.truth}
                        </span>
                      ) : isFalse ? (
                        <span className="flex items-center gap-1 text-[10px] bg-error-50 dark:bg-error-950/40 text-error-600 dark:text-error-400 font-bold border border-error-500/25 px-2 py-0.5 rounded-full shrink-0">
                          <X size={10} /> {item.truth}
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-[10px] bg-warning-50 dark:bg-warning-950/40 text-warning-700 dark:text-warning-400 font-bold border border-warning-500/25 px-2 py-0.5 rounded-full shrink-0">
                          <AlertCircle size={10} /> {item.truth}
                        </span>
                      )}
                      <h5 className="font-bold text-neutral-950 dark:text-neutral-100 leading-tight flex-1">
                        {item.claim}
                      </h5>
                    </div>
                    <p className="text-[11px] text-neutral-500 dark:text-neutral-400 leading-relaxed font-medium pl-1">
                      {item.explanation}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Q&A Interactive Deep Analysis */}
        <div className="space-y-3 pt-2 border-t border-neutral-100 dark:border-neutral-800/80">
          <h4 className="text-[10px] font-bold text-neutral-400 dark:text-neutral-500 uppercase tracking-widest flex items-center gap-1.5">
            <HelpCircle size={14} className="text-neutral-400" /> 심층 질문 및 추가 검증
          </h4>

          {/* Chat logs */}
          <div className="space-y-2.5 max-h-[220px] overflow-y-auto pr-1">
            {chatHistory.length === 0 ? (
              <p className="text-[11px] text-neutral-400 italic font-medium pl-1">
                이 기사에서 더 알고 싶은 사실이 있다면 아래에 질문해 보세요. (예: &quot;진짜 사건 관련 정부 입장이 있나?&quot;)
              </p>
            ) : (
              chatHistory.map((chat, idx) => (
                <div key={idx} className="space-y-1.5">
                  <div className="flex justify-end">
                    <span className="bg-neutral-100 dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100 px-3 py-1.5 rounded-2xl rounded-tr-none text-xs font-bold shadow-sm max-w-[85%]">
                      {chat.query}
                    </span>
                  </div>
                  <div className="flex justify-start">
                    <div className="bg-info-50/60 dark:bg-info-950/30 border border-info-500/20 dark:border-info-500/20 text-neutral-800 dark:text-neutral-200 px-3 py-2 rounded-2xl rounded-tl-none text-xs font-semibold shadow-sm max-w-[85%] leading-relaxed">
                      {chat.loading ? (
                        <span className="flex items-center gap-1.5 text-neutral-500 dark:text-neutral-400 font-bold">
                          <Loader2 size={12} className="animate-spin" /> 실시간 보도 검색 및 AI 분석 중...
                        </span>
                      ) : (
                        chat.answer
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Chat input */}
          <form onSubmit={onChatSubmit} className="flex gap-2">
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="추가 질문을 입력해 주세요..."
              disabled={loadingChat}
              className="flex-1 bg-neutral-50 dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-800 rounded-md px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 dark:focus:ring-brand-400/30 dark:focus:border-brand-400 text-neutral-900 dark:text-neutral-100"
            />
            <button
              type="submit"
              disabled={loadingChat || !chatInput.trim()}
              className="bg-brand-500 hover:bg-brand-600 active:bg-brand-700 text-white rounded-md p-2 shrink-0 disabled:opacity-40 flex items-center justify-center transition-colors"
            >
              <Send size={14} />
            </button>
          </form>
        </div>

        {/* Emoji Reactions */}
        <div className="space-y-3 pt-2 border-t border-neutral-100 dark:border-neutral-800/80">
          <h4 className="text-[10px] font-bold text-neutral-400 dark:text-neutral-500 uppercase tracking-widest">
            리액션 남기기
          </h4>
          <div className="flex gap-2.5">
            {["👍", "👎", "😮", "😡"].map(emoji => {
              const reaction = reactions.find(r => r.emoji === emoji);
              const isReacted = !!userReactions[emoji];
              return (
                <button
                  key={emoji}
                  onClick={() => onAddReaction(emoji)}
                  className={`flex items-center gap-1.5 border rounded-md px-3.5 py-1.5 text-xs font-bold transition-all shadow-sm active:scale-95 ${
                    isReacted
                      ? "bg-brand-50 dark:bg-brand-900/40 border-brand-500/50 dark:border-brand-400/40 text-brand-600 dark:text-brand-300"
                      : "bg-neutral-50 dark:bg-neutral-800 border-neutral-200 dark:border-neutral-800 text-neutral-900 dark:text-neutral-100 hover:bg-neutral-100 dark:hover:bg-neutral-700"
                  }`}
                >
                  <span>{emoji}</span>
                  <span className={`font-mono text-[10px] ${isReacted ? "text-brand-500 dark:text-brand-300" : "text-neutral-400"}`}>
                    {reaction ? reaction.count : 0}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Community Comments */}
        <div className="space-y-3 pt-2 border-t border-neutral-100 dark:border-neutral-800/80">
          <h4 className="text-[10px] font-bold text-neutral-400 dark:text-neutral-500 uppercase tracking-widest flex items-center gap-1.5">
            <MessageSquare size={14} className="text-neutral-400" /> 댓글 모음 ({comments.length}건)
          </h4>

          {/* Comments list */}
          <div className="space-y-2 max-h-[200px] overflow-y-auto pr-1">
            {comments.length === 0 ? (
              <p className="text-[11px] text-neutral-400 italic pl-1">첫 댓글을 작성해 보세요!</p>
            ) : (
              comments.map((comment, index) => (
                <div
                  key={index}
                  className="bg-neutral-50 dark:bg-neutral-800 border border-neutral-200/60 dark:border-neutral-800 rounded-lg p-3 text-xs space-y-1"
                >
                  <div className="flex justify-between items-center text-[10px] font-bold text-neutral-400">
                    <span>👤 {comment.author}</span>
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-medium text-[9px]">
                        {comment.created_at ? new Date(comment.created_at).toLocaleDateString() : ""}
                      </span>
                      {(comment.user_token === userToken || !comment.user_token) && (
                        <button
                          onClick={() => onDeleteComment(comment.id)}
                          className="text-neutral-400 hover:text-error-500 p-0.5 rounded transition-colors"
                          title="댓글 삭제"
                        >
                          <X size={12} />
                        </button>
                      )}
                    </div>
                  </div>
                  <p className="text-neutral-700 dark:text-neutral-300 leading-normal pl-0.5">
                    {comment.content}
                  </p>
                </div>
              ))
            )}
          </div>

          {/* Comment inputs */}
          <form onSubmit={onAddComment} className="space-y-2">
            <div className="flex gap-2">
              <input
                type="text"
                value={commentAuthor}
                onChange={(e) => setCommentAuthor(e.target.value)}
                placeholder="이름 (익명)"
                maxLength="15"
                className="w-1/3 bg-neutral-50 dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-800 rounded-md px-2.5 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 dark:focus:ring-brand-400/30 dark:focus:border-brand-400 text-neutral-900 dark:text-neutral-100"
              />
              <input
                type="text"
                value={commentContent}
                onChange={(e) => setCommentContent(e.target.value)}
                placeholder="공동 팩트체크를 위한 댓글을 적어주세요..."
                required
                className="flex-1 bg-neutral-50 dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-800 rounded-md px-2.5 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 dark:focus:ring-brand-400/30 dark:focus:border-brand-400 text-neutral-900 dark:text-neutral-100"
              />
            </div>
            <button
              type="submit"
              disabled={!commentContent.trim()}
              className="w-full bg-brand-500 hover:bg-brand-600 active:bg-brand-700 text-white font-bold text-xs py-2 rounded-md transition-all shadow-sm disabled:opacity-40"
            >
              댓글 등록
            </button>
          </form>
        </div>

        {/* Search references list */}
        {selectedItem.sources && selectedItem.sources.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-[10px] font-bold text-neutral-400 dark:text-neutral-500 uppercase tracking-widest">
              📡 실시간 웹 교차 수집 출처 ({selectedItem.sources?.length || 0}건)
            </h4>
            <div className="space-y-2.5 max-h-[320px] overflow-y-auto pr-1">
              {selectedItem.sources.map((src, index) => (
                <div 
                  key={index}
                  className="bg-neutral-50 dark:bg-neutral-800 border border-neutral-200/60 dark:border-neutral-800 rounded-lg p-3.5 text-xs space-y-1.5 hover:border-neutral-300 dark:hover:border-neutral-700 transition-colors shadow-sm"
                >
                  <div className="flex justify-between items-start gap-2">
                    <h5 className="font-bold text-neutral-950 dark:text-neutral-100 line-clamp-1 flex-1 leading-tight">
                      {src.title}
                    </h5>
                    <a 
                      href={src.link} 
                      target="_blank" 
                      rel="noreferrer"
                      className="text-brand-500 hover:text-brand-600 dark:text-brand-300 dark:hover:text-brand-200 shrink-0"
                    >
                      <ExternalLink size={12} />
                    </a>
                  </div>
                  <p className="text-[11px] text-neutral-400 leading-relaxed line-clamp-2">
                    {src.description}
                  </p>
                  <div className="text-[9px] text-neutral-400/80 font-mono text-right">
                    {src.pub_date || src.pubDate}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

      </div>

      {/* Panel Delete Actions */}
      <div className="border-t border-neutral-200 dark:border-neutral-800/80 pt-4 mt-6 flex gap-2">
        <button 
          onClick={(e) => onDeleteItem(selectedItem.id, e)}
          className="flex-1 border border-error-500/25 dark:border-error-500/25 hover:bg-error-50 dark:hover:bg-error-950/20 text-error-600 dark:text-error-400 py-2.5 rounded-lg font-bold text-xs transition-colors flex items-center justify-center gap-1.5"
        >
          <Trash2 size={14} /> 레포트 삭제
        </button>
      </div>

    </div>
  );
}
