"use client";

import { useState, FormEvent } from "react";

interface Props {
  onSend: (content: string) => void;
  disabled: boolean;
}

export function ChatInput({ onSend, disabled }: Props) {
  const [input, setInput] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setInput("");
  };

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-3">
      <div
        className="relative flex-1"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Search for a product..."
          disabled={disabled}
          className="w-full rounded-xl px-4 py-3 text-sm transition-all duration-200 focus:outline-none disabled:opacity-40"
          style={{
            background: 'var(--bg-chat)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border)',
            boxShadow: 'var(--shadow-sm)',
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = 'var(--accent)';
            e.currentTarget.style.boxShadow = '0 0 0 3px var(--accent-soft)';
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = 'var(--border)';
            e.currentTarget.style.boxShadow = 'var(--shadow-sm)';
          }}
        />
      </div>
      <button
        type="submit"
        disabled={disabled || !input.trim()}
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-white transition-all duration-150 hover:scale-[1.04] active:scale-[0.96] disabled:opacity-30 disabled:hover:scale-100"
        style={{ background: 'var(--accent)' }}
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 10.5L12 3m0 0l7.5 7.5M12 3v18" />
        </svg>
      </button>
    </form>
  );
}
