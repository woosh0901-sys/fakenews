import React from "react";
import { Shield, Sun, Moon } from "lucide-react";

export default function HeaderMobile({ darkMode, setDarkMode, onLogoClick }) {
  return (
    <header className="lg:hidden flex justify-between items-center px-6 py-4 border-b border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 z-20">
      <button
        type="button"
        onClick={onLogoClick}
        title="메인 페이지로 이동"
        className="flex items-center gap-2"
      >
        <div className="p-1.5 bg-brand-500 rounded-md text-white">
          <Shield size={18} />
        </div>
        <span className="font-bold text-sm bg-clip-text text-transparent bg-gradient-to-r from-brand-500 to-secondary-600 dark:from-brand-300 dark:to-secondary-400">
          Fake News Defender
        </span>
      </button>
      <button 
        onClick={() => setDarkMode(!darkMode)}
        className="p-2 border border-neutral-200 dark:border-neutral-800 rounded-md hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-500 dark:text-neutral-400"
        title="테마 전환"
      >
        {darkMode ? <Sun size={16} /> : <Moon size={16} />}
      </button>
    </header>
  );
}
