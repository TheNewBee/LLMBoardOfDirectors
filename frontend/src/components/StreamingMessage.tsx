import { agentColor } from "./MessageBubble";

type Props = {
  agentId: string;
  agentName: string;
  role: string;
  content: string;
};

export function StreamingMessage({ agentId, agentName, role, content }: Props) {
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
          <span className="message-role-tag">{role}</span>
        </div>
        <div className="message-content">
          {content}
          <span className="cursor-blink" aria-hidden="true" />
        </div>
      </div>
    </div>
  );
}
