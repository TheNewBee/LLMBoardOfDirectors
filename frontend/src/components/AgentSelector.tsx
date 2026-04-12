import type { AgentSummary } from "../api";

type Props = {
  agents: AgentSummary[];
  modelOptions: string[];
  selected: string[];
  modelsByAgent: Record<string, string>;
  onChange: (next: string[]) => void;
  onModelsChange: (next: Record<string, string>) => void;
};

export function AgentSelector({
  agents,
  modelOptions,
  selected,
  modelsByAgent,
  onChange,
  onModelsChange
}: Props) {
  const toggle = (agentId: string) => {
    if (selected.includes(agentId)) {
      onChange(selected.filter((item) => item !== agentId));
      const next = { ...modelsByAgent };
      delete next[agentId];
      onModelsChange(next);
      return;
    }
    if (selected.length >= 6) {
      return;
    }
    onChange([...selected, agentId]);
  };

  return (
    <section className="card setup-card">
      <div className="card-heading">
        <p className="eyebrow">Agents</p>
        <h3>Select 2–6 voices</h3>
      </div>
      <div className="agent-grid" aria-label="Available agents">
        {agents.map((agent) => (
          <button
            key={agent.id}
            className={selected.includes(agent.id) ? "chip chip-active" : "chip"}
            onClick={() => toggle(agent.id)}
            type="button"
            aria-pressed={selected.includes(agent.id)}
            title={agent.expertise_domain}
          >
            {agent.name}
          </button>
        ))}
      </div>
      {selected.length > 0 && modelOptions.length > 0 ? (
        <div className="agent-models">
          <h4>Per-agent models</h4>
          {selected.map((agentId) => (
            <label className="field" key={agentId}>
              {agentId}
              <select
                value={modelsByAgent[agentId] ?? ""}
                onChange={(event) => {
                  const value = event.target.value;
                  const next = { ...modelsByAgent };
                  if (!value) {
                    delete next[agentId];
                  } else {
                    next[agentId] = value;
                  }
                  onModelsChange(next);
                }}
              >
                <option value="">Default model</option>
                {modelOptions.map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>
      ) : null}
    </section>
  );
}
