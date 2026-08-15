import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import Landing from "./Landing";
import Sidebar from "./components/Sidebar";
import HeaderMobile from "./components/HeaderMobile";
import SearchSection from "./components/SearchSection";
import RankingsSection from "./components/RankingsSection";
import HistorySection from "./components/HistorySection";
import DiagnosticPanel from "./components/DiagnosticPanel";
import AssistantChatTab from "./components/AssistantChatTab";

const API_BASE_URL = "/api";

export default function App() {
  // Timer references for memory cleanup
  const activeTimersRef = useRef([]);

  // Theme state
  const [darkMode, setDarkMode] = useState(() => {
    return localStorage.getItem("theme") === "dark" || 
      (!localStorage.getItem("theme") && window.matchMedia("(prefers-color-scheme: dark)").matches);
  });

  // View state: 첫 접속은 랜딩, 검증 시작/대시보드 보기 클릭 시 대시보드로 전환
  const [view, setView] = useState("landing");

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
    avg_contradiction_score: 0
  });

  // Ranking & Interaction States
  const [rankings, setRankings] = useState({ most_checked: [], top_fakes: [] });
  const [comments, setComments] = useState([]);
  const [reactions, setReactions] = useState([]);
  const [chatHistory, setChatHistory] = useState([]);
  const [commentAuthor, setCommentAuthor] = useState("");
  const [commentContent, setCommentContent] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [loadingChat, setLoadingChat] = useState(false);

  // General Chatbot States
  const [activeTab, setActiveTab] = useState("dashboard");
  const [generalChatHistory, setGeneralChatHistory] = useState([
    {
      query: null,
      answer: "안녕하세요! 실시간 웹 검색과 RAG-LLM 기반의 AI 팩트체커 어시스턴트입니다. 궁금한 소문, 뉴스, 루머에 대해 질문하시면 실시간으로 관련 사실을 추적하고 검증 결과를 알려드립니다. (예: '성수대교 단차 9cm 사실인가요?')",
      sources: [],
      isSystem: true
    }
  ]);
  const [generalChatInput, setGeneralChatInput] = useState("");
  const [loadingGeneralChat, setLoadingGeneralChat] = useState(false);
  
  // Persistent anonymous user identity
  const [userToken] = useState(() => {
    let token = localStorage.getItem("user_token");
    if (!token) {
      token = "user_" + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
      localStorage.setItem("user_token", token);
    }
    return token;
  });
  const [userReactions, setUserReactions] = useState({});

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

  // Load rankings
  const loadRankings = async () => {
    try {
      const res = await axios.get(`${API_BASE_URL}/stats/rankings`);
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

  // Load comments, reactions, and chat history when selectedItem changes
  useEffect(() => {
    if (!selectedItem || selectedItem.id === null || selectedItem.id === undefined) {
      setComments([]);
      setReactions([]);
      setChatHistory([]);
      setUserReactions({});
      return;
    }
    
    const loadItemDetails = async () => {
      try {
        const [commentsRes, reactionsRes] = await Promise.all([
          axios.get(`${API_BASE_URL}/history/${selectedItem.id}/comments`),
          axios.get(`${API_BASE_URL}/history/${selectedItem.id}/reactions`)
        ]);
        setComments(Array.isArray(commentsRes.data) ? commentsRes.data : []);
        setReactions(Array.isArray(reactionsRes.data) ? reactionsRes.data : []);
        setChatHistory([]);
        
        // Load user's local reactions for this item
        const savedReactions = JSON.parse(localStorage.getItem(`reacted_${selectedItem.id}`) || "{}");
        setUserReactions(savedReactions);
      } catch (err) {
        console.error("댓글/리액션 로드 실패:", err);
      }
    };
    
    loadItemDetails();
  }, [selectedItem]);

  // Cleanup all active timers on unmount
  useEffect(() => {
    return () => {
      activeTimersRef.current.forEach(clearTimeout);
      activeTimersRef.current = [];
    };
  }, []);

  // 검증 실행
  const runCheck = async (targetUrl) => {
    if (loading || !targetUrl.trim()) return;

    activeTimersRef.current.forEach(clearTimeout);
    activeTimersRef.current = [];

    setLoading(true);
    setActiveStep(1);
    
    // 3단계 로딩 스텝 시뮬레이션
    const t2 = setTimeout(() => setActiveStep(2), 1400);
    const t3 = setTimeout(() => setActiveStep(3), 2800);
    
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
        setSelectedItem({
          ...res.data,
          title: res.data.title ?? res.data.target_title,
          url: res.data.url ?? res.data.target_url,
        });
      }, 400);
      
      activeTimersRef.current.push(tSuccess);
      
    } catch (err) {
      activeTimersRef.current.forEach(clearTimeout);
      activeTimersRef.current = [];
      setLoading(false);
      const errMsg = err.response?.data?.detail || "탐지 분석 중 기술적 에러가 발생했습니다.";
      alert(errMsg);
    }
  };

  const handleCheck = (e) => {
    e.preventDefault();
    runCheck(urlInput);
  };

  const handleLandingSubmit = (inputVal) => {
    const trimmed = inputVal.trim();
    const isUrl = trimmed.startsWith("http://") || 
                  trimmed.startsWith("https://") || 
                  (trimmed.split('/')[0].includes('.') && !trimmed.includes(' '));
                  
    if (isUrl) {
      setUrlInput(trimmed);
      setActiveTab("dashboard");
      setView("dashboard");
      runCheck(trimmed);
    } else {
      setActiveTab("assistant");
      setView("dashboard");
      setSelectedItem(null);
      handleGeneralChatSubmit(null, trimmed);
    }
  };

  const handleDelete = async (id, e) => {
    if (e) e.stopPropagation();
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
    
    if (selectedItem.id === null || selectedItem.id === undefined) {
      alert("데이터베이스에 저장되지 않은 임시 검사 결과에는 댓글을 남길 수 없습니다.");
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

  const handleAddReaction = async (emoji) => {
    if (!selectedItem) return;
    
    if (selectedItem.id === null || selectedItem.id === undefined) {
      alert("데이터베이스에 저장되지 않은 임시 검사 결과에는 리액션을 남길 수 없습니다.");
      return;
    }
    
    const isAlreadyReacted = !!userReactions[emoji];
    
    try {
      const res = await axios.post(`${API_BASE_URL}/history/${selectedItem.id}/reactions`, {
        emoji,
        is_canceling: isAlreadyReacted
      });
      
      const updatedUserReactions = { ...userReactions };
      if (isAlreadyReacted) {
        delete updatedUserReactions[emoji];
      } else {
        updatedUserReactions[emoji] = true;
      }
      setUserReactions(updatedUserReactions);
      localStorage.setItem(`reacted_${selectedItem.id}`, JSON.stringify(updatedUserReactions));
      
      const updatedReactions = [...reactions];
      const idx = updatedReactions.findIndex(r => r.emoji === emoji);
      if (idx > -1) {
        updatedReactions[idx].count = res.data.count;
      } else {
        updatedReactions.push(res.data);
      }
      setReactions(updatedReactions);
    } catch (err) {
      const errMsg = err.response?.data?.detail || err.message || "알 수 없는 에러";
      alert("리액션 저장 실패: " + errMsg);
    }
  };

  const handleChatSubmit = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || loadingChat || !selectedItem) return;
    
    if (selectedItem.id === null || selectedItem.id === undefined) {
      alert("데이터베이스에 저장되지 않은 검사 결과에는 Q&A 질문을 할 수 없습니다.");
      return;
    }
    
    const query = chatInput.trim();
    setChatInput("");
    setLoadingChat(true);
    
    const tempChat = [...chatHistory, { query, answer: null, loading: true }];
    setChatHistory(tempChat);
    
    try {
      const res = await axios.post(`${API_BASE_URL}/check/${selectedItem.id}/query`, {
        query
      });
      
      setChatHistory(prev => prev.map(item => 
        item.query === query && item.loading 
          ? { query, answer: res.data.answer, loading: false } 
          : item
      ));
    } catch (err) {
      const errMsg = err.response?.data?.detail || err.message || "추가 분석 중 에러가 발생했습니다.";
      setChatHistory(prev => prev.map(item => 
        item.query === query && item.loading 
          ? { query, answer: `추가 분석 중 에러가 발생했습니다. (${errMsg})`, loading: false } 
          : item
      ));
    } finally {
      setLoadingChat(false);
    }
  };

  const handleGeneralChatSubmit = async (e, customQuery = null) => {
    if (e) e.preventDefault();
    const query = (customQuery || generalChatInput).trim();
    if (!query || loadingGeneralChat) return;

    setGeneralChatInput("");
    setLoadingGeneralChat(true);

    const tempChat = [...generalChatHistory, { query, answer: null, sources: [], loading: true }];
    setGeneralChatHistory(tempChat);

    try {
      const res = await axios.post(`${API_BASE_URL}/chat`, { query });
      setGeneralChatHistory(prev => prev.map(item => 
        item.query === query && item.loading 
          ? { query, answer: res.data.answer, sources: res.data.sources, loading: false } 
          : item
      ));
    } catch (err) {
      const errMsg = err.response?.data?.detail || err.message || "답변을 불러오지 못했습니다.";
      setGeneralChatHistory(prev => prev.map(item => 
        item.query === query && item.loading 
          ? { query, answer: `분석 중 에러가 발생했습니다: ${errMsg}`, sources: [], loading: false } 
          : item
      ));
    } finally {
      setLoadingGeneralChat(false);
    }
  };

  const getVerdictBadge = (verdict) => {
    switch (verdict) {
      case "REAL":
        return (
          <span className="flex items-center gap-1.5 w-fit bg-success-50 dark:bg-success-950/30 text-success-700 dark:text-success-400 text-xs px-2.5 py-1 rounded-full font-bold border border-success-500/25 dark:border-success-500/25">
            <span className="w-1.5 h-1.5 rounded-full bg-success-500 animate-pulse"></span>
            진짜 뉴스
          </span>
        );
      case "FAKE":
        return (
          <span className="flex items-center gap-1.5 w-fit bg-error-50 dark:bg-error-950/30 text-error-600 dark:text-error-400 text-xs px-2.5 py-1 rounded-full font-bold border border-error-500/25 dark:border-error-500/25">
            <span className="w-1.5 h-1.5 rounded-full bg-error-500 animate-pulse"></span>
            가짜 뉴스
          </span>
        );
      case "SUSPICIOUS":
      default:
        return (
          <span className="flex items-center gap-1.5 w-fit bg-warning-50 dark:bg-warning-950/30 text-warning-700 dark:text-warning-400 text-xs px-2.5 py-1 rounded-full font-bold border border-warning-500/25 dark:border-warning-500/25">
            <span className="w-1.5 h-1.5 rounded-full bg-warning-500 animate-pulse"></span>
            의심/과장
          </span>
        );
    }
  };

  const loaderSteps = [
    { label: "1. 본문 수집", desc: "웹페이지 크롤링 및 전처리" },
    { label: "2. 교차 검색", desc: "포털 API & 웹 실시간 추적" },
    { label: "3. 사실 검증", desc: "Gemini 클라우드 정밀 대조" }
  ];

  // 랜딩 뷰 렌더링
  if (view === "landing") {
    return (
      <Landing
        darkMode={darkMode}
        setDarkMode={setDarkMode}
        history={history}
        loading={loading}
        onSubmit={handleLandingSubmit}
        onOpenDashboard={() => setView("dashboard")}
      />
    );
  }

  return (
    <div className="min-h-screen xl:h-screen xl:overflow-hidden bg-neutral-50 dark:bg-neutral-950 text-neutral-900 dark:text-neutral-100 flex transition-colors duration-200 font-sans">
      
      {/* Desktop Sidebar */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        stats={stats}
        darkMode={darkMode}
        setDarkMode={setDarkMode}
        onLogoClick={() => setView("landing")}
      />

      {/* Main Area */}
      <div className="flex-1 flex flex-col min-w-0 xl:min-h-0">
        
        {/* Mobile Header */}
        <HeaderMobile
          darkMode={darkMode}
          setDarkMode={setDarkMode}
          onLogoClick={() => setView("landing")}
        />

        {/* Content Wrapper */}
        <div className="flex-1 flex flex-col xl:flex-row overflow-x-hidden min-h-0">
          
          {activeTab === "dashboard" ? (
            <>
              {/* Dashboard Main Scrollable Pane */}
              <div className={`flex-1 p-6 space-y-6 overflow-y-auto max-w-full ${selectedItem ? "xl:w-2/3" : "w-full"} transition-all duration-300`}>
                
                {/* Search & Verification Input */}
                <SearchSection
                  urlInput={urlInput}
                  setUrlInput={setUrlInput}
                  loading={loading}
                  activeStep={activeStep}
                  loaderSteps={loaderSteps}
                  onCheck={handleCheck}
                  onQuickFill={(sampleUrl) => {
                    setUrlInput(sampleUrl);
                    runCheck(sampleUrl);
                  }}
                />

                {/* Real-time Rankings */}
                <RankingsSection
                  rankings={rankings}
                  history={history}
                  onSelectItem={(item) => setSelectedItem(item)}
                />

                {/* History Table */}
                <HistorySection
                  history={history}
                  selectedItem={selectedItem}
                  onSelectItem={(item) => setSelectedItem(item)}
                  onDeleteItem={handleDelete}
                  getVerdictBadge={getVerdictBadge}
                />

              </div>

              {/* Slide-over Diagnostic Detail Panel */}
              <DiagnosticPanel
                selectedItem={selectedItem}
                onClose={() => setSelectedItem(null)}
                onDeleteItem={handleDelete}
                getVerdictBadge={getVerdictBadge}
                chatHistory={chatHistory}
                chatInput={chatInput}
                setChatInput={setChatInput}
                loadingChat={loadingChat}
                onChatSubmit={handleChatSubmit}
                reactions={reactions}
                userReactions={userReactions}
                onAddReaction={handleAddReaction}
                comments={comments}
                commentAuthor={commentAuthor}
                setCommentAuthor={setCommentAuthor}
                commentContent={commentContent}
                setCommentContent={setCommentContent}
                userToken={userToken}
                onAddComment={handleAddComment}
                onDeleteComment={handleDeleteComment}
              />
            </>
          ) : (
            /* AI Assistant Chatbot Tab */
            <AssistantChatTab
              generalChatHistory={generalChatHistory}
              setGeneralChatHistory={setGeneralChatHistory}
              generalChatInput={generalChatInput}
              setGeneralChatInput={setGeneralChatInput}
              loadingGeneralChat={loadingGeneralChat}
              onGeneralChatSubmit={handleGeneralChatSubmit}
            />
          )}

        </div>

      </div>

    </div>
  );
}
