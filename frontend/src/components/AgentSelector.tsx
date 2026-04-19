import { useEffect, useRef, useState } from "react";
import type { AgentSummary } from "../api";
import { agentColor } from "./MessageBubble";
import { SearchableModelList } from "./SearchableModelList";

type Props = {
  available: AgentSummary[];
  selected: string[];
  modelsByAgent: Record<string, string>;
  modelOptions: string[];
  disabled: boolean;
  onChange: (next: string[]) => void;
  onModelsChange: (next: Record<string, string>) => void;
};

export function AgentSelector({
  available,
  selected,
  modelsByAgent,
  modelOptions,
  disabled,
  onChange,
  onModelsChange,
}: Props) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [modelPopover, setModelPopover] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
        setModelPopover(null);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const toggleAgent = (id: string) => {
    if (disabled) return;
    if (selected.includes(id)) {
      onChange(selected.filter((s) => s !== id));
      const next = { ...modelsByAgent };
      delete next[id];
      onModelsChange(next);
    } else if (selected.length < 6) {
      onChange([...selected, id]);
      setDropdownOpen(false);
    }
  };

  const setModel = (agentId: string, model: string) => {
    const next = { ...modelsByAgent };
    if (!model) delete next[agentId];
    else next[agentId] = model;
    onModelsChange(next);
    setModelPopover(null);
  };

  const unselected = available.filter((a) => !selected.includes(a.id));
  const selectedAgents = selected
    .map((id) => available.find((a) => a.id === id))
    .filter((a): a is AgentSummary => Boolean(a));

  return (
    <div className="header-agents" ref={dropdownRef}>
      {selectedAgents.map((agent) => {
        const color = agentColor(agent.id);
        const model = modelsByAgent[agent.id];
        return (
          <div key={agent.id} style={{ position: "relative", display: "inline-flex", alignItems: "center", gap: "0.2rem" }}>
            <button
              className={`agent-chip selected${disabled ? " disabled-chip" : ""}`}
              onClick={() => !disabled && toggleAgent(agent.id)}
              title={agent.expertise_domain}
              type="button"
            >
              <span className="agent-chip-dot" style={{ background: color }} />
              {agent.name}
              {!disabled && (
                <span
                  className="agent-chip-remove"
                  role="button"
                  aria-label={`Remove ${agent.name}`}
                  onClick={(e) => { e.stopPropagation(); toggleAgent(agent.id); }}
                >
                  ×
                </span>
              )}
            </button>
            {modelOptions.length > 0 && (
              <button
                className="model-popover-trigger"
                title="Override model"
                onClick={() => setModelPopover(modelPopover === agent.id ? null : agent.id)}
                disabled={disabled}
              >
                {model ? model.split("/").pop() : "default"}
              </button>
            )}
            {modelPopover === agent.id && (
              <div className="agent-dropdown" style={{ left: 0, top: "calc(100% + 4px)", minWidth: 280 }}>
                <div className="agent-dropdown-header">Model for {agent.name}</div>
                <div style={{ padding: "0 0.5rem 0.5rem" }}>
                  <SearchableModelList
                    id={`model-search-${agent.id}`}
                    options={modelOptions}
                    value={model ?? ""}
                    onChange={(next) => setModel(agent.id, next)}
                    defaultOptionLabel="Default"
                    emptyMessage="No matching models."
                  />
                </div>
              </div>
            )}
          </div>
        );
      })}

      {!disabled && selected.length < 6 && unselected.length > 0 && (
        <div style={{ position: "relative" }}>
          <button
            className="agent-add-btn"
            onClick={() => setDropdownOpen(!dropdownOpen)}
            title="Add agent"
            type="button"
          >
            +
          </button>
          {dropdownOpen && (
            <div className="agent-dropdown">
              <div className="agent-dropdown-header">Add agent</div>
              {unselected.map((agent) => (
                <button
                  key={agent.id}
                  className="agent-dropdown-item"
                  onClick={() => toggleAgent(agent.id)}
                  title={agent.expertise_domain}
                >
                  <span className="agent-chip-dot" style={{ background: agentColor(agent.id), flexShrink: 0 }} />
                  <span>
                    {agent.name}
                    <small style={{ display: "block" }}>{agent.expertise_domain}</small>
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
