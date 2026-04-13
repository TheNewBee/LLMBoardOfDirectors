import { useEffect, useRef, type KeyboardEvent } from "react";
import { SearchableModelList } from "./SearchableModelList";

type Props = {
  open: boolean;
  hasApiKey: boolean;
  apiKeyDraft: string;
  defaultModel: string;
  temperature: number;
  webSearchEnabled: boolean;
  modelOptions: string[];
  onApiKeyDraftChange: (next: string) => void;
  onSaveApiKey: () => void;
  onValidateApiKey: () => void;
  onDefaultModelChange: (next: string) => void;
  onTemperatureChange: (next: number) => void;
  onWebSearchEnabledChange: (next: boolean) => void;
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
  onApiKeyDraftChange,
  onSaveApiKey,
  onValidateApiKey,
  onDefaultModelChange,
  onTemperatureChange,
  onWebSearchEnabledChange,
  onClose,
}: Props) {
  const drawerRef = useRef<HTMLElement | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    window.requestAnimationFrame(() => {
      const firstControl = drawerRef.current?.querySelector<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );
      (firstControl ?? drawerRef.current)?.focus();
    });
    return () => { previousFocusRef.current?.focus(); };
  }, [open]);

  if (!open) return null;

  const handleKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === "Escape") { event.preventDefault(); onClose(); return; }
    if (event.key !== "Tab" || !drawerRef.current) return;
    const focusable = Array.from(
      drawerRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )
    );
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  };

  return (
    <div className="drawer-backdrop" onClick={onClose} role="presentation">
      <aside
        ref={drawerRef}
        className="drawer"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        tabIndex={-1}
      >
        <button className="icon-btn drawer-close-btn" onClick={onClose} aria-label="Close settings">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
          </svg>
        </button>

        <h3 id="settings-title" className="drawer-title">Settings</h3>

        <div className="settings-section">
          <h4>API Access</h4>
          <label className="field-label">OpenRouter API key</label>
          <div className="inline-row">
            <input
              type="password"
              className="field-input"
              value={apiKeyDraft}
              onChange={(e) => onApiKeyDraftChange(e.target.value)}
              placeholder={hasApiKey ? "Key stored — paste to replace" : "sk-or-..."}
            />
          </div>
          <div className="inline-row">
            <button className="btn-primary" type="button" onClick={onSaveApiKey}>
              Save key
            </button>
            <button className="btn-secondary" type="button" onClick={onValidateApiKey}>
              Validate
            </button>
          </div>
        </div>

        <div className="settings-section">
          <h4>Model defaults</h4>
          <SearchableModelList
            id="default-model-search"
            label="Default model"
            options={modelOptions}
            value={defaultModel}
            onChange={onDefaultModelChange}
            emptyMessage="No matching models."
          />
          <label className="field-label" style={{ marginTop: "0.5rem" }}>
            Temperature — {temperature.toFixed(2)}
          </label>
          <input
            type="range"
            min={0}
            max={2}
            step={0.05}
            value={temperature}
            onChange={(e) => onTemperatureChange(Number(e.target.value))}
            style={{ width: "100%", accentColor: "var(--accent)" }}
          />
          <p className="field-hint">Higher = more creative, lower = more focused.</p>
        </div>

        <div className="settings-section">
          <h4>Tools</h4>
          <div className="toggle-row">
            <span className="toggle-label">Web search</span>
            <label className="toggle">
              <input
                type="checkbox"
                checked={webSearchEnabled}
                onChange={(e) => onWebSearchEnabledChange(e.target.checked)}
              />
              <span className="toggle-slider" />
            </label>
          </div>
          <p className="field-hint">python_exec is disabled in web mode for safety.</p>
        </div>
      </aside>
    </div>
  );
}
