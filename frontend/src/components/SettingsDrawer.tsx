type Props = {
  open: boolean;
  hasApiKey: boolean;
  apiKeyDraft: string;
  defaultModel: string;
  temperature: number;
  webSearchEnabled: boolean;
  modelOptions: string[];
  knowledgeStatus: Array<{ agent_id: string; stale: boolean; last_refresh: string | null }>;
  onApiKeyDraftChange: (next: string) => void;
  onSaveApiKey: () => void;
  onValidateApiKey: () => void;
  onDefaultModelChange: (next: string) => void;
  onTemperatureChange: (next: number) => void;
  onWebSearchEnabledChange: (next: boolean) => void;
  onRefreshKnowledge: () => void;
  onClose: () => void;
};

export function SettingsDrawer({
  open,
  hasApiKey,
  apiKeyDraft,
  defaultModel,
  temperature,
  webSearchEnabled,
  modelOptions,
  knowledgeStatus,
  onApiKeyDraftChange,
  onSaveApiKey,
  onValidateApiKey,
  onDefaultModelChange,
  onTemperatureChange,
  onWebSearchEnabledChange,
  onRefreshKnowledge,
  onClose
}: Props) {
  if (!open) {
    return null;
  }
  return (
    <div className="drawer-backdrop" onClick={onClose} role="presentation">
      <aside className="drawer" onClick={(event) => event.stopPropagation()}>
        <h3>Settings</h3>
        <label>
          OpenRouter API key
          <input
            type="password"
            value={apiKeyDraft}
            onChange={(event) => onApiKeyDraftChange(event.target.value)}
            placeholder={hasApiKey ? "Stored key available" : "Enter key"}
          />
        </label>
        <div className="inline-row">
          <button type="button" onClick={onSaveApiKey}>
            Save key
          </button>
          <button type="button" className="secondary" onClick={onValidateApiKey}>
            Validate key
          </button>
        </div>
        <label>
          Default model
          <select value={defaultModel} onChange={(event) => onDefaultModelChange(event.target.value)}>
            {modelOptions.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
        </label>
        <label>
          Temperature ({temperature.toFixed(2)})
          <input
            type="range"
            min={0}
            max={2}
            step={0.05}
            value={temperature}
            onChange={(event) => onTemperatureChange(Number(event.target.value))}
          />
        </label>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={webSearchEnabled}
            onChange={(event) => onWebSearchEnabledChange(event.target.checked)}
          />
          Enable web_search tool
        </label>
        <p className="muted">
          <strong>python_exec</strong> is disabled in web mode for safety.
        </p>
        <div className="knowledge">
          <h4>Knowledge status</h4>
          <button type="button" className="secondary" onClick={onRefreshKnowledge}>
            Refresh stale knowledge
          </button>
          <ul>
            {knowledgeStatus.map((item) => (
              <li key={item.agent_id}>
                {item.agent_id}: {item.stale ? "stale" : "fresh"}{" "}
                <small>{item.last_refresh ?? "never refreshed"}</small>
              </li>
            ))}
          </ul>
        </div>
        <button onClick={onClose} type="button">
          Close
        </button>
      </aside>
    </div>
  );
}

