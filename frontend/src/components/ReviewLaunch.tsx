type Props = {
  briefingText: string;
  agents: string[];
  disabled: boolean;
  onLaunch: () => void;
};

export function ReviewLaunch({ briefingText, agents, disabled, onLaunch }: Props) {
  const hasBriefing = briefingText.trim().length > 0;

  return (
    <section className="card launch-card">
      <div className="card-heading">
        <p className="eyebrow">Launch checklist</p>
        <h3>Ready to start?</h3>
      </div>
      <p className="launch-summary">{hasBriefing ? briefingText : "Add a briefing topic to continue."}</p>
      <p className="muted">Agents: {agents.length ? agents.join(", ") : "None selected"}</p>
      <button disabled={disabled} onClick={onLaunch} type="button">
        Start meeting
      </button>
    </section>
  );
}
