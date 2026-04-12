export type MeetingEvent =
  | { type: "meeting_started"; meeting_id: string }
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

