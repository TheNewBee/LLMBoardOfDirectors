import { useEffect, useMemo, useState } from "react";
import {
  fetchAgents,
  fetchActiveMeetings,
  fetchConfig,
  fetchKnowledgeStatus,
  fetchModels,
  refreshKnowledge,
  storeKey,
  updateConfig,
  validateKey,
  type AgentSummary
} from "./api";
import { AgentSelector } from "./components/AgentSelector";
import { BriefingDialog } from "./components/BriefingDialog";
import { MeetingControls } from "./components/MeetingControls";
import { MeetingStatus } from "./components/MeetingStatus";
import { MessageBubble } from "./components/MessageBubble";
import { OutputsPanel } from "./components/OutputsPanel";
import { ReviewLaunch } from "./components/ReviewLaunch";
import { SettingsDrawer } from "./components/SettingsDrawer";
import { Sidebar } from "./components/Sidebar";
import { useMeetingSocket } from "./hooks/useMeetingSocket";
import type { BriefingForm } from "./types";

const initialBriefing: BriefingForm = {
  text: "",
  objectives: ""
};

function defaultSelection(agents: AgentSummary[]): string[] {
  if (agents.length === 0) {
    return ["adversary", "strategist"];
  }
  const adversary = agents.find((agent) => agent.id === "adversary")?.id;
  const fallback = agents.find((agent) => agent.id !== adversary)?.id;
  const picks = [adversary, fallback].filter(Boolean) as string[];
  return picks.length >= 2 ? picks : agents.slice(0, 2).map((agent) => agent.id);
}

export default function App() {
  const [briefing, setBriefing] = useState<BriefingForm>(initialBriefing);
  const [availableAgents, setAvailableAgents] = useState<AgentSummary[]>([]);
  const [agents, setAgents] = useState<string[]>([]);
  const [modelsByAgent, setModelsByAgent] = useState<Record<string, string>>({});
  const [modelOptions, setModelOptions] = useState<string[]>([]);
  const [defaultModel, setDefaultModel] = useState("");
  const [temperature, setTemperature] = useState(0.7);
  const [webSearchEnabled, setWebSearchEnabled] = useState(true);
  const [hasApiKey, setHasApiKey] = useState(false);
  const [apiKeyDraft, setApiKeyDraft] = useState("");
  const [knowledgeStatus, setKnowledgeStatus] = useState<
    Array<{ agent_id: string; stale: boolean; last_refresh: string | null }>
  >([]);
  const [toast, setToast] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [history, setHistory] = useState<Array<{ id: string; status: string }>>([]);
  const socket = useMeetingSocket();

  const events = socket.events;
  const turnStarts = events.filter((event) => event.type === "turn_start");
  const messages = events.filter((event) => event.type === "turn_complete");
  const activeSpeaker =
    turnStarts.length > 0 ? turnStarts[turnStarts.length - 1].agent_name : null;
  const outputsEvent = [...events]
    .reverse()
    .find((event) => event.type === "meeting_complete" || event.type === "meeting_cancelled");
  const outputs = outputsEvent ? outputsEvent.outputs : null;

  const canStart = useMemo(() => {
    return (
      briefing.text.trim().length > 0 &&
      agents.length >= 2 &&
      agents.includes("adversary") &&
      socket.status !== "running" &&
      socket.status !== "connecting"
    );
  }, [briefing.text, agents, socket.status]);

  const startMeeting = () => {
    const objectives = briefing.objectives
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
    socket.connectAndStart({
      briefing: { text: briefing.text, objectives },
      agents,
      models_by_agent: modelsByAgent,
      enable_web_search: webSearchEnabled
    });
  };

  const createNewMeeting = () => {
    socket.reset();
    setBriefing(initialBriefing);
    setAgents(defaultSelection(availableAgents));
    setModelsByAgent({});
  };

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [agentsPayload, configPayload, modelsPayload, knowledgePayload] = await Promise.all([
          fetchAgents(),
          fetchConfig(),
          fetchModels().catch(() => []),
          fetchKnowledgeStatus().catch(() => [])
        ]);
        if (cancelled) {
          return;
        }
        setAvailableAgents(agentsPayload);
        setAgents(defaultSelection(agentsPayload));
        setDefaultModel(configPayload.config.default_model.model);
        setTemperature(configPayload.config.default_model.temperature);
        setWebSearchEnabled(configPayload.config.web_search.provider !== "tavily_disabled");
        setHasApiKey(configPayload.has_openrouter_api_key);
        setModelOptions(modelsPayload.length ? modelsPayload : [configPayload.config.default_model.model]);
        setKnowledgeStatus(knowledgePayload);
      } catch (error) {
        setToast((error as Error).message);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const active = await fetchActiveMeetings();
        if (cancelled) {
          return;
        }
        setHistory((prev) => {
          const fromApi = active.map((item) => ({ id: item.meeting_id, status: item.status }));
          const remainder = prev.filter((item) => !fromApi.some((apiItem) => apiItem.id === item.id));
          return [...fromApi, ...remainder].slice(0, 20);
        });
      } catch {
        // Non-fatal: keep existing history state.
      }
    };
    void tick();
    const timer = window.setInterval(() => {
      void tick();
    }, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    const terminalEvent = [...events]
      .reverse()
      .find((event) => event.type === "meeting_complete" || event.type === "meeting_cancelled");
    if (!terminalEvent) {
      return;
    }
    setHistory((prev) => {
      if (prev.some((item) => item.id === terminalEvent.meeting_id)) {
        return prev;
      }
      return [
        { id: terminalEvent.meeting_id, status: terminalEvent.type.replace("meeting_", "") },
        ...prev
      ];
    });
  }, [events]);

  const persistConfig = async (patch: Record<string, unknown>, successMessage: string) => {
    try {
      await updateConfig(patch);
      setToast(successMessage);
    } catch (error) {
      setToast((error as Error).message);
    }
  };

  const handleSaveApiKey = async () => {
    if (!apiKeyDraft.trim()) {
      setToast("Enter an API key first.");
      return;
    }
    const ok = await storeKey("openrouter", apiKeyDraft.trim());
    setHasApiKey(ok);
    setApiKeyDraft("");
    setToast(ok ? "API key saved." : "Failed to save API key.");
  };

  const handleValidateApiKey = async () => {
    const ok = await validateKey("openrouter", defaultModel);
    setToast(ok ? "API key is valid." : "API key validation failed.");
  };

  const handleRefreshKnowledge = async () => {
    try {
      const result = await refreshKnowledge();
      const updated = await fetchKnowledgeStatus();
      setKnowledgeStatus(updated);
      setToast(
        `Knowledge refresh: refreshed=${result.refreshed.length}, failed=${result.failed.length}`
      );
    } catch (error) {
      setToast((error as Error).message);
    }
  };

  return (
    <div className="layout">
      <Sidebar
        meetings={history}
        onNewMeeting={createNewMeeting}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <main className="main">
        {toast ? <div className="toast">{toast}</div> : null}
        <BriefingDialog value={briefing} onChange={setBriefing} />
        <AgentSelector
          agents={availableAgents}
          modelOptions={modelOptions}
          selected={agents}
          modelsByAgent={modelsByAgent}
          onChange={setAgents}
          onModelsChange={setModelsByAgent}
        />
        <ReviewLaunch
          briefingText={briefing.text}
          agents={agents}
          disabled={!canStart}
          onLaunch={startMeeting}
        />

        <section className="card">
          <h3>Live Meeting</h3>
          <MeetingStatus
            status={socket.status}
            activeSpeaker={activeSpeaker}
            turns={messages.length}
          />
          <MeetingControls canCancel={socket.status === "running"} onCancel={socket.cancel} />
          <div className="message-list">
            {messages.length === 0 ? (
              <p className="muted">No turns yet.</p>
            ) : (
              messages.map((message, idx) => (
                <MessageBubble
                  key={`${message.agent_id}-${idx}`}
                  agentId={message.agent_id}
                  agentName={message.agent_name}
                  content={message.content}
                />
              ))
            )}
          </div>
        </section>

        <OutputsPanel outputs={outputs} />
      </main>
      <SettingsDrawer
        open={settingsOpen}
        hasApiKey={hasApiKey}
        apiKeyDraft={apiKeyDraft}
        defaultModel={defaultModel}
        temperature={temperature}
        webSearchEnabled={webSearchEnabled}
        modelOptions={modelOptions}
        knowledgeStatus={knowledgeStatus}
        onApiKeyDraftChange={setApiKeyDraft}
        onSaveApiKey={handleSaveApiKey}
        onValidateApiKey={handleValidateApiKey}
        onDefaultModelChange={(next) => {
          setDefaultModel(next);
          void persistConfig(
            { default_model: { model: next } },
            "Default model updated."
          );
        }}
        onTemperatureChange={(next) => {
          setTemperature(next);
          void persistConfig(
            { default_model: { temperature: next } },
            "Temperature updated."
          );
        }}
        onWebSearchEnabledChange={(next) => {
          setWebSearchEnabled(next);
          setToast(
            next
              ? "Web search enabled for new meetings."
              : "Web search disabled for new meetings."
          );
        }}
        onRefreshKnowledge={handleRefreshKnowledge}
        onClose={() => setSettingsOpen(false)}
      />
    </div>
  );
}

