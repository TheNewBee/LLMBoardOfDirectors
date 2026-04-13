import { useRef, useState, useEffect, KeyboardEvent } from "react";

type Props = {
  status: string;
  onStart: (briefing: { text: string; objectives: string[] }) => void;
  onCancel: () => void;
  onReset: () => void;
};

export function ChatInput({ status, onStart, onCancel, onReset }: Props) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const idle = status === "idle";
  const running = status === "running" || status === "connecting" || status === "recovering";
  const cancelling = status === "cancelling";
  const done = status === "done" || status === "error";

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [text]);

  const submit = () => {
    const trimmed = text.trim();
    if (!trimmed) return;
    onStart({ text: trimmed, objectives: [] });
    setText("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (idle && text.trim()) submit();
    }
  };

  if (done) {
    return (
      <div className="chat-input-area">
        <button className="chat-new-meeting-btn" onClick={onReset}>
          + Start a new discussion
        </button>
      </div>
    );
  }

  if (running || cancelling) {
    return (
      <div className="chat-input-area">
        <div className="chat-input-box" style={{ alignItems: "center" }}>
          <span className="chat-status-text" style={{ flex: 1, textAlign: "left" }}>
            {cancelling ? "Cancelling..." : "Board is deliberating..."}
          </span>
          {running && (
            <button className="chat-cancel-btn" onClick={onCancel}>
              Stop
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="chat-input-area">
      <div className="chat-input-box">
        <textarea
          ref={textareaRef}
          className="chat-input-field"
          placeholder="What should the board discuss?"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={!idle}
        />
        <button
          className="chat-send-btn"
          onClick={submit}
          disabled={!text.trim()}
          aria-label="Send"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 13V3M3 8l5-5 5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </div>
  );
}
