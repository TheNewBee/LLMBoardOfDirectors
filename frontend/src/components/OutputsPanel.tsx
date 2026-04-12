type Outputs = {
  transcript: string | null;
  kill_sheet: string | null;
  consensus_roadmap: string | null;
};

type Props = {
  outputs: Outputs | null;
};

export function OutputsPanel({ outputs }: Props) {
  return (
    <section className="card">
      <h3>Outputs</h3>
      {!outputs ? (
        <p className="muted">Outputs will appear after meeting completion.</p>
      ) : (
        <ul className="outputs-list">
          <li>Transcript: {outputs.transcript ?? "N/A"}</li>
          <li>Kill sheet: {outputs.kill_sheet ?? "N/A"}</li>
          <li>Consensus roadmap: {outputs.consensus_roadmap ?? "N/A"}</li>
        </ul>
      )}
    </section>
  );
}

