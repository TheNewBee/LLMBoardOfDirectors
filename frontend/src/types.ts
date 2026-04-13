export type MeetingEvent =
  | { type: "meeting_started"; meeting_id: string }
  | { type: "turn_chunk"; meeting_id: string; agent_id: string; chunk: string }
  | {
      type: "meeting_state.v2";
      version: "2";
      meeting_id: string;
      phase: "prepare" | "live" | "recover" | "wrap_up";
      status: "running" | "waiting_retry" | "recovered" | "completed" | "failed_terminal";
      error_category:
        | "none"
        | "rate_limited"
        | "provider_unavailable"
        | "timeout"
        | "missing_api_key"
        | "unknown";
      terminal: boolean;
      retry: {
        attempt: number | null;
        max_attempts: number | null;
        next_retry_ms: number | null;
      };
      user_message: string;
      ts: string;
    }
  | {
      type: "turn_start";
      meeting_id: string;
      agent_id: string;
      agent_name: string;
      role: string;
      turn_number: number;
    }
  | {
      type: "turn_complete";
      meeting_id: string;
      agent_id: string;
      agent_name: string;
      content: string;
      timestamp: string;
      tool_results: Array<Record<string, unknown>>;
    }
  | {
      type: "meeting_complete";
      meeting_id: string;
      termination_reason: string | null;
      outputs: {
        transcript: string | null;
        kill_sheet: string | null;
        consensus_roadmap: string | null;
      };
    }
  | {
      type: "meeting_cancelled";
      meeting_id: string;
      outputs: {
        transcript: string | null;
        kill_sheet: string | null;
        consensus_roadmap: string | null;
      };
    }
  | {
      type: "error";
      code: string;
      message: string;
      fatal: boolean;
    };

export type BriefingForm = {
  text: string;
  objectives: string;
};

