// Deterministic per-agent color derived from id
export function agentColor(agentId: string): string {
  const palette = [
    "#10a37f", "#6366f1", "#f59e0b", "#ef4444",
    "#3b82f6", "#ec4899", "#8b5cf6", "#14b8a6",
  ];
  let hash = 0;
  for (let i = 0; i < agentId.length; i++) {
    hash = (hash * 31 + agentId.charCodeAt(i)) & 0xffffffff;
  }
  return palette[Math.abs(hash) % palette.length];
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

type Props = {
  agentId: string;
  agentName: string;
  role?: string;
  content: string;
  timestamp?: string;
  toolCount?: number;
};

export function MessageBubble({ agentId, agentName, role, content, timestamp, toolCount }: Props) {
  const color = agentColor(agentId);
  const initial = agentName.charAt(0).toUpperCase();

  return (
    <div className="message-row">
      <div className="avatar" style={{ background: color }}>
        {initial}
      </div>
      <div className="message-body">
        <div className="message-header-row">
          <span className="message-agent-name">{agentName}</span>
          {role && <span className="message-role-tag">{role}</span>}
          {timestamp && <span className="message-timestamp">{formatTime(timestamp)}</span>}
        </div>
        <div className="message-content">{content}</div>
        {toolCount != null && toolCount > 0 && (
          <div className="message-tool-badge">
            <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
              <path d="M9 1L11 3l-6 6H3V7l6-6z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
            </svg>
            {toolCount} tool {toolCount === 1 ? "call" : "calls"}
          </div>
        )}
      </div>
    </div>
  );
}
