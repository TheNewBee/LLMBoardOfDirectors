type Props = {
  briefingText: string;
  agents: string[];
  disabled: boolean;
  onLaunch: () => void;
};

export function ReviewLaunch({ briefingText, agents, disabled, onLaunch }: Props) {
  return (
    <section className="card">
      <h3>3. Review and Launch</h3>
      <p className="muted">{briefingText || "Add a briefing topic to continue."}</p>
      <p className="muted">Agents: {agents.length ? agents.join(", ") : "None selected"}</p>
      <button disabled={disabled} onClick={onLaunch} type="button">
        Start Meeting
      </button>
    </section>
  );
}

