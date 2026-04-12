type Props = {
  agentId: string;
  agentName: string;
  content: string;
};

export function MessageBubble({ agentId, agentName, content }: Props) {
  return (
    <article className="message">
      <header>
        <span className="badge">{agentName}</span>
        <small>{agentId}</small>
      </header>
      <p>{content}</p>
    </article>
  );
}

