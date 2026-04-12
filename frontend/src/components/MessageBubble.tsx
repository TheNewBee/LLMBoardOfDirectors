type Props = {
  agentId: string;
  agentName: string;
  content: string;
  timestamp?: string;
  toolCount?: number;
  turnNumber?: number;
};

function formatTimestamp(timestamp?: string): string | null {
  if (!timestamp) {
    return null;
  }
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) {
    return timestamp;
  }
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit"
  }).format(parsed);
}

export function MessageBubble({ agentId, agentName, content, timestamp, toolCount = 0, turnNumber }: Props) {
  const timeLabel = formatTimestamp(timestamp);

  return (
    <article className="message">
      <header className="message-header">
        <div>
          <span className="message-agent">{agentName}</span>
          <span className="message-id">{agentId}</span>
        </div>
        <div className="message-meta">
          {turnNumber ? <span>Turn {turnNumber}</span> : null}
          {timeLabel && timestamp ? <time dateTime={timestamp}>{timeLabel}</time> : null}
          {toolCount > 0 ? <span>{toolCount} tool result{toolCount === 1 ? "" : "s"}</span> : null}
        </div>
      </header>
      <p className="message-content">{content}</p>
    </article>
  );
}
