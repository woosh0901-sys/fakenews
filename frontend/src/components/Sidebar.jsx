import React from "react";
import { Shield, Database, MessageSquare, Sun, Moon } from "lucide-react";

export default function Sidebar({
  activeTab,
  setActiveTab,
  stats,
  darkMode,
  setDarkMode,
  onLogoClick
}) {
  return (
    <aside className="hidden lg:flex w-80 shrink-0 flex-col bg-white dark:bg-neutral-900 border-r border-neutral-200 dark:border-neutral-800 p-6 sticky top-0 h-screen justify-between shadow-sm z-30 font-sans">
      <div className="space-y-8">
        
        {/* Logo (클릭 시 랜딩으로 복귀) */}
        <div
          className="flex items-center gap-3 cursor-pointer select-none"
          onClick={onLogoClick}
          title="메인 페이지로 이동"
        >
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
        
        {/* Navigation Menu */}
        <div className="space-y-1">
          <button
            onClick={() => setActiveTab("dashboard")}
            className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === "dashboard"
                ? "bg-brand-500 text-white shadow-md shadow-brand-500/15"
                : "text-neutral-500 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800"
            }`}
          >
            <Database size={14} />
            신뢰도 대시보드
          </button>
          <button
            onClick={() => setActiveTab("assistant")}
            className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === "assistant"
                ? "bg-brand-500 text-white shadow-md shadow-brand-500/15"
                : "text-neutral-500 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800"
            }`}
          >
            <MessageSquare size={14} />
            AI 팩트체크 어시스턴트
          </button>
        </div>

        {/* Stats Section */}
        <div className="space-y-4">
          <h2 className="text-xs font-bold text-neutral-400 dark:text-neutral-500 uppercase tracking-widest">
            실시간 탐지 현황
          </h2>
          
          {/* 총 검사 + 판정 분포 스택 바 (한눈에 비율 파악) */}
          <div className="bg-neutral-50 dark:bg-neutral-800 border border-neutral-200/60 dark:border-neutral-800 rounded-lg p-4 shadow-sm space-y-3.5">
            <div className="flex items-baseline justify-between">
              <span className="text-[10px] text-neutral-400 font-bold uppercase tracking-wider">총 검사</span>
              <span className="text-2xl font-bold font-mono text-neutral-950 dark:text-neutral-50 leading-none">
                {stats.total_checks}
              </span>
            </div>

            <div className="flex h-2 w-full rounded-full overflow-hidden bg-neutral-200 dark:bg-neutral-700">
              <div
                className="bg-success-500 transition-all duration-500"
                style={{ width: `${(stats.real_count / Math.max(stats.total_checks, 1)) * 100}%` }}
              />
              <div
                className="bg-error-500 transition-all duration-500"
                style={{ width: `${(stats.fake_count / Math.max(stats.total_checks, 1)) * 100}%` }}
              />
              <div
                className="bg-warning-500 transition-all duration-500"
                style={{ width: `${(stats.suspicious_count / Math.max(stats.total_checks, 1)) * 100}%` }}
              />
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div>
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-success-500 shrink-0" />
                  <span className="text-[10px] text-neutral-500 dark:text-neutral-400 font-bold">진짜</span>
                </div>
                <p className="text-lg font-bold font-mono text-success-600 dark:text-success-400 mt-0.5 leading-none">
                  {stats.real_count}
                </p>
              </div>
              <div>
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-error-500 shrink-0" />
                  <span className="text-[10px] text-neutral-500 dark:text-neutral-400 font-bold">가짜</span>
                </div>
                <p className="text-lg font-bold font-mono text-error-600 dark:text-error-400 mt-0.5 leading-none">
                  {stats.fake_count}
                </p>
              </div>
              <div>
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-warning-500 shrink-0" />
                  <span className="text-[10px] text-neutral-500 dark:text-neutral-400 font-bold">의심</span>
                </div>
                <p className="text-lg font-bold font-mono text-warning-600 dark:text-warning-400 mt-0.5 leading-none">
                  {stats.suspicious_count}
                </p>
              </div>
            </div>
          </div>

          {/* Performance Averages */}
          <div className="bg-neutral-50 dark:bg-neutral-800 border border-neutral-200/60 dark:border-neutral-800 rounded-lg p-4 space-y-3">
            <div className="flex justify-between items-center text-xs">
              <span className="text-neutral-500 dark:text-neutral-400 font-medium">평균 모순 점수</span>
              <span className="font-mono font-bold text-neutral-950 dark:text-neutral-50">
                {(stats.avg_contradiction_score || 0).toFixed(2)}
              </span>
            </div>
            <div className="w-full bg-neutral-200 dark:bg-neutral-800 h-1.5 rounded-full overflow-hidden">
              <div 
                className="bg-brand-500 dark:bg-brand-400 h-full transition-all duration-500" 
                style={{ width: `${(stats.avg_contradiction_score || 0) * 100}%` }}
              />
            </div>
          </div>

        </div>

      </div>

      {/* Sidebar Footer */}
      <div className="pt-4 border-t border-neutral-200 dark:border-neutral-800 flex items-center justify-between">
        <span className="text-xs text-neutral-400 dark:text-neutral-500 font-medium">Powered by Gemini 2.5</span>
        <button 
          onClick={() => setDarkMode(!darkMode)}
          className="p-2 border border-neutral-200 dark:border-neutral-800 rounded-md hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors text-neutral-500 dark:text-neutral-400"
          title="테마 전환"
        >
          {darkMode ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </div>
    </aside>
  );
}
