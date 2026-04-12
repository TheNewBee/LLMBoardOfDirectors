type Outputs = {
  transcript: string | null;
  kill_sheet: string | null;
  consensus_roadmap: string | null;
};

type Props = {
  outputs: Outputs | null;
};

const outputLabels: Array<{ key: keyof Outputs; label: string }> = [
  { key: "transcript", label: "Transcript" },
  { key: "kill_sheet", label: "Kill sheet" },
  { key: "consensus_roadmap", label: "Consensus roadmap" }
];

export function OutputsPanel({ outputs }: Props) {
  if (!outputs) {
    return (
      <section className="outputs-panel outputs-panel-empty" aria-label="Meeting artifacts">
        <p className="eyebrow">Artifacts</p>
        <p className="muted">Transcript, kill sheet, and consensus roadmap appear here when the meeting ends.</p>
      </section>
    );
  }

  return (
    <section className="outputs-panel" aria-label="Meeting artifacts">
      <div>
        <p className="eyebrow">Artifacts ready</p>
        <h2>Meeting outputs</h2>
      </div>
      <ul className="outputs-list">
        {outputLabels.map((item) => (
          <li key={item.key}>
            <span>{item.label}</span>
            <code>{outputs[item.key] ?? "N/A"}</code>
          </li>
        ))}
      </ul>
    </section>
  );
}
