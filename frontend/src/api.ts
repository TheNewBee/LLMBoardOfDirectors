export type AgentSummary = {
  id: string;
  name: string;
  role: string;
  expertise_domain: string;
  personality_traits: string[];
  biases: string[];
  bias_intensity: number;
};

export type ConfigPayload = {
  default_model: {
    provider: string;
    model: string;
    temperature: number;
    max_tokens: number;
  };
  agent_models: Record<string, { provider: string; model: string; temperature: number; max_tokens: number }>;
  web_search: {
    provider: string;
  };
  vector_store: {
    enabled: boolean;
  };
};

export async function fetchAgents(): Promise<AgentSummary[]> {
  const response = await fetch("/api/agents");
  if (!response.ok) {
    throw new Error("Failed to load agents.");
  }
  const payload = await response.json();
  return payload.agents as AgentSummary[];
}

export async function fetchConfig(): Promise<{
  config: ConfigPayload;
  has_openrouter_api_key: boolean;
}> {
  const response = await fetch("/api/config");
  if (!response.ok) {
    throw new Error("Failed to load config.");
  }
  return response.json();
}

export async function updateConfig(patch: Record<string, unknown>): Promise<void> {
  const response = await fetch("/api/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ patch })
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to update config.");
  }
}

export async function validateKey(provider = "openrouter", model?: string): Promise<boolean> {
  const response = await fetch("/api/config/validate-key", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, model: model ?? null })
  });
  if (!response.ok) {
    return false;
  }
  const payload = await response.json();
  return Boolean(payload.ok);
}

export async function storeKey(provider: string, apiKey: string): Promise<boolean> {
  const response = await fetch("/api/config/keys", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, api_key: apiKey, validate_after_store: true })
  });
  if (!response.ok) {
    return false;
  }
  const payload = await response.json();
  return Boolean(payload.ok);
}

export async function fetchModels(provider = "openrouter"): Promise<string[]> {
  const response = await fetch(`/api/config/models?provider=${encodeURIComponent(provider)}`);
  if (!response.ok) {
    throw new Error("Failed to load models.");
  }
  const payload = await response.json();
  return (payload.models as Array<{ id: string }>).map((item) => item.id);
}

export async function fetchKnowledgeStatus(): Promise<
  Array<{ agent_id: string; last_refresh: string | null; stale: boolean }>
> {
  const response = await fetch("/api/knowledge/status");
  if (!response.ok) {
    throw new Error("Failed to load knowledge status.");
  }
  const payload = await response.json();
  return payload.items;
}

export async function refreshKnowledge(): Promise<{
  refreshed: string[];
  failed: string[];
  skipped: string[];
}> {
  const response = await fetch("/api/knowledge/refresh", { method: "POST" });
  if (!response.ok) {
    throw new Error("Failed to refresh knowledge.");
  }
  return response.json();
}

export async function fetchActiveMeetings(): Promise<Array<{ meeting_id: string; status: string }>> {
  const response = await fetch("/api/meetings");
  if (!response.ok) {
    throw new Error("Failed to load meetings.");
  }
  const payload = await response.json();
  return payload.meetings;
}

