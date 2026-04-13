import { useEffect, useMemo, useRef, useState } from "react";
import {
  fetchAgents,
  fetchConfig,
  fetchModels,
  storeKey,
  updateConfig,
  validateKey,
  type AgentSummary,
} from "./api";
import { AgentSelector } from "./components/AgentSelector";
import { ChatInput } from "./components/ChatInput";
import { MessageBubble } from "./components/MessageBubble";
import { SettingsDrawer } from "./components/SettingsDrawer";
import { StreamingMessage } from "./components/StreamingMessage";
import { useMeetingSocket } from "./hooks/useMeetingSocket";

// Deterministic default: adversary + first non-adversary agent
function defaultSelection(agents: AgentSummary[]): string[] {
  if (agents.length === 0) return ["adversary", "strategist"];
  const adversary = agents.find((a) => a.id === "adversary")?.id;
  const fallback = agents.find((a) => a.id !== adversary)?.id;
  const picks = [adversary, fallback].filter(Boolean) as string[];
  return picks.length >= 2 ? picks : agents.slice(0, 2).map((a) => a.id);
}

type SystemMessage = {
  id: string;
  text: string;
  variant: "info" | "error" | "success";
};

export default function App() {
  const [availableAgents, setAvailableAgents] = useState<AgentSummary[]>([]);
  const [selectedAgents, setSelectedAgents] = useState<string[]>([]);
  const [modelsByAgent, setModelsByAgent] = useState<Record<string, string>>({});
  const [modelOptions, setModelOptions] = useState<string[]>([]);
  const [defaultModel, setDefaultModel] = useState("");
  const [temperature, setTemperature] = useState(0.7);
  const [webSearchEnabled, setWebSearchEnabled] = useState(true);
  const [hasApiKey, setHasApiKey] = useState(false);
  const [apiKeyDraft, setApiKeyDraft] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [systemMessages, setSystemMessages] = useState<SystemMessage[]>([]);

  const socket = useMeetingSocket();
  const chatBottomRef = useRef<HTMLDivElement>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isBusy = useMemo(
    () =>
      socket.status === "connecting" ||
      socket.status === "running" ||
      socket.status === "recovering" ||
      socket.status === "cancelling",
    [socket.status]
  );

  // Load initial config/agents
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [agents, config, models] = await Promise.all([
          fetchAgents(),
          fetchConfig(),
          fetchModels().catch(() => [] as string[]),
        ]);
        if (cancelled) return;
        setAvailableAgents(agents);
        setSelectedAgents(defaultSelection(agents));
        setDefaultModel(config.config.default_model.model);
        setTemperature(config.config.default_model.temperature);
        setWebSearchEnabled(config.config.web_search.provider !== "tavily_disabled");
        setHasApiKey(config.has_openrouter_api_key);
        setModelOptions(models.length ? models : [config.config.default_model.model]);
      } catch (err) {
        showToast((err as Error).message);
      }
    };
    void load();
    return () => { cancelled = true; };
  }, []);

  // Auto-scroll to bottom when messages or streaming content changes
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [socket.messages, socket.streamingMessage?.content]);

  // Show system messages on key events
  useEffect(() => {
    if (socket.status === "done" && socket.outputs) {
      addSystemMessage("Meeting complete.", "success");
    }
  }, [socket.status]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (socket.errorMessage) {
      addSystemMessage(socket.errorMessage, "error");
    }
  }, [socket.errorMessage]);

  const addSystemMessage = (text: string, variant: SystemMessage["variant"] = "info") => {
    setSystemMessages((prev) => [
      ...prev,
      { id: `sys-${Date.now()}-${Math.random()}`, text, variant },
    ]);
  };

  const showToast = (msg: string) => {
    setToast(msg);
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => setToast(null), 3500);
  };

  const handleStart = (briefing: { text: string; objectives: string[] }) => {
    setSystemMessages([{ id: "start", text: `Discussing: "${briefing.text}"`, variant: "info" }]);
    socket.connectAndStart({
      briefing,
      agents: selectedAgents,
      models_by_agent: modelsByAgent,
      enable_web_search: webSearchEnabled,
    });
  };

  const handleReset = () => {
    socket.reset();
    setSystemMessages([]);
  };

  const handleSaveApiKey = async () => {
    if (!apiKeyDraft.trim()) { showToast("Enter an API key first."); return; }
    const ok = await storeKey("openrouter", apiKeyDraft.trim());
    setHasApiKey(ok);
    setApiKeyDraft("");
    showToast(ok ? "API key saved." : "Failed to save API key.");
  };

  const handleValidateApiKey = async () => {
    const ok = await validateKey("openrouter", defaultModel);
    showToast(ok ? "API key is valid." : "API key validation failed.");
  };

  const persistConfig = async (patch: Record<string, unknown>, msg: string) => {
    try {
      await updateConfig(patch);
      showToast(msg);
    } catch (err) {
      showToast((err as Error).message);
    }
  };

  const hasMessages = socket.messages.length > 0 || socket.streamingMessage !== null;

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <span className="header-brand">Boardroom</span>
        <AgentSelector
          available={availableAgents}
          selected={selectedAgents}
          modelsByAgent={modelsByAgent}
          modelOptions={modelOptions}
          disabled={isBusy}
          onChange={setSelectedAgents}
          onModelsChange={setModelsByAgent}
        />
        <div className="header-actions">
          <button
            className="icon-btn"
            onClick={() => setSettingsOpen(true)}
            aria-label="Settings"
            title="Settings"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="2.5" stroke="currentColor" strokeWidth="1.4"/>
              <path d="M8 1v1.5M8 13.5V15M1 8h1.5M13.5 8H15M3.05 3.05l1.06 1.06M11.89 11.89l1.06 1.06M3.05 12.95l1.06-1.06M11.89 4.11l1.06-1.06" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
            </svg>
          </button>
        </div>
      </header>

      {/* Chat area */}
      <div className="chat-area" role="log" aria-live="polite" aria-label="Board discussion">
        {!hasMessages && systemMessages.length === 0 ? (
          <div className="empty-state">
            <h2>Start a board discussion</h2>
            <p>
              Select your board members above, then type a topic below.
              The board will deliberate in real time.
            </p>
          </div>
        ) : null}

        {systemMessages.map((sm) => (
          <div key={sm.id} className="system-msg">
            <span className={`system-msg-inner${sm.variant === "error" ? " error" : sm.variant === "success" ? " success" : ""}`}>
              {sm.text}
            </span>
          </div>
        ))}

        {socket.messages.map((msg, idx) => (
          <MessageBubble
            key={`${msg.meetingId}-${msg.agentId}-${msg.timestamp}-${idx}`}
            agentId={msg.agentId}
            agentName={msg.agentName}
            content={msg.content}
            timestamp={msg.timestamp}
            toolCount={msg.toolResults.length}
          />
        ))}

        {socket.streamingMessage && (
          <StreamingMessage
            agentId={socket.streamingMessage.agentId}
            agentName={socket.streamingMessage.agentName}
            role={socket.streamingMessage.role}
            content={socket.streamingMessage.content}
          />
        )}

        {socket.status === "recovering" && (
          <div className="system-msg">
            <span className="system-msg-inner" style={{ color: "var(--warning)" }}>
              Recovering from provider error, retrying...
            </span>
          </div>
        )}

        <div ref={chatBottomRef} />
      </div>

      {/* Input */}
      <ChatInput
        status={socket.status}
        onStart={handleStart}
        onCancel={socket.cancel}
        onReset={handleReset}
      />

      {/* Settings drawer */}
      <SettingsDrawer
        open={settingsOpen}
        hasApiKey={hasApiKey}
        apiKeyDraft={apiKeyDraft}
        defaultModel={defaultModel}
        temperature={temperature}
        webSearchEnabled={webSearchEnabled}
        modelOptions={modelOptions}
        onApiKeyDraftChange={setApiKeyDraft}
        onSaveApiKey={handleSaveApiKey}
        onValidateApiKey={handleValidateApiKey}
        onDefaultModelChange={(next) => {
          setDefaultModel(next);
          void persistConfig({ default_model: { model: next } }, "Default model updated.");
        }}
        onTemperatureChange={(next) => {
          setTemperature(next);
          void persistConfig({ default_model: { temperature: next } }, "Temperature updated.");
        }}
        onWebSearchEnabledChange={(next) => {
          setWebSearchEnabled(next);
          showToast(next ? "Web search enabled." : "Web search disabled.");
        }}
        onClose={() => setSettingsOpen(false)}
      />

      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}
