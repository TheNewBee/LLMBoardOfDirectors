import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export type CompletedMessage = {
  meetingId: string;
  agentId: string;
  agentName: string;
  content: string;
  timestamp: string;
  toolResults: Array<Record<string, unknown>>;
};

export type StreamingMessage = {
  agentId: string;
  agentName: string;
  role: string;
  content: string;
  turnNumber: number;
};

type StartPayload = {
  briefing: { text: string; objectives: string[] };
  agents: string[];
  models_by_agent?: Record<string, string>;
  enable_web_search?: boolean;
};

export type MeetingOutputs = {
  transcript: string | null;
  kill_sheet: string | null;
  consensus_roadmap: string | null;
};

export function useMeetingSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const [messages, setMessages] = useState<CompletedMessage[]>([]);
  const [streamingMessage, setStreamingMessage] = useState<StreamingMessage | null>(null);
  const [status, setStatus] = useState("idle");
  const [outputs, setOutputs] = useState<MeetingOutputs | null>(null);
  const [meetingId, setMeetingId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const connectAndStart = useCallback((payload: StartPayload) => {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/meeting`);
    wsRef.current = ws;
    setStatus("connecting");
    setMessages([]);
    setStreamingMessage(null);
    setOutputs(null);
    setErrorMessage(null);

    ws.onopen = () => {
      setStatus("running");
      ws.send(JSON.stringify({ type: "start_meeting", ...payload }));
    };

    ws.onmessage = (event) => {
      const parsed = JSON.parse(event.data as string) as Record<string, unknown>;

      switch (parsed.type) {
        case "meeting_started":
          setMeetingId(parsed.meeting_id as string);
          break;

        case "turn_start":
          setStreamingMessage({
            agentId: parsed.agent_id as string,
            agentName: parsed.agent_name as string,
            role: parsed.role as string,
            content: "",
            turnNumber: parsed.turn_number as number,
          });
          setStatus("running");
          break;

        case "turn_chunk":
          setStreamingMessage((prev) =>
            prev ? { ...prev, content: prev.content + (parsed.chunk as string) } : prev
          );
          break;

        case "turn_complete":
          setStreamingMessage(null);
          setMessages((prev) => [
            ...prev,
            {
              meetingId: parsed.meeting_id as string,
              agentId: parsed.agent_id as string,
              agentName: parsed.agent_name as string,
              content: parsed.content as string,
              timestamp: parsed.timestamp as string,
              toolResults: parsed.tool_results as Array<Record<string, unknown>>,
            },
          ]);
          setStatus("running");
          break;

        case "meeting_state.v2": {
          const stateEvent = parsed as Record<string, unknown>;
          if ((stateEvent.phase as string) === "recover" && !(stateEvent.terminal as boolean)) {
            setStatus("recovering");
          } else if ((stateEvent.terminal as boolean) && (stateEvent.status as string) === "failed_terminal") {
            setStatus("error");
            setErrorMessage(stateEvent.user_message as string);
          }
          break;
        }

        case "meeting_complete":
        case "meeting_cancelled":
          setStreamingMessage(null);
          setOutputs(parsed.outputs as MeetingOutputs);
          setStatus("done");
          break;

        case "error":
          setStreamingMessage(null);
          setStatus("error");
          setErrorMessage(parsed.message as string);
          break;
      }
    };

    ws.onerror = () => {
      setStatus("error");
      setErrorMessage("Connection error. Please check the server is running.");
    };

    ws.onclose = () => {
      if (status === "running" || status === "connecting" || status === "recovering") {
        setStatus("error");
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const cancel = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "cancel" }));
      setStatus("cancelling");
    }
  }, []);

  const reset = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    setMessages([]);
    setStreamingMessage(null);
    setStatus("idle");
    setOutputs(null);
    setMeetingId(null);
    setErrorMessage(null);
  }, []);

  useEffect(() => {
    return () => wsRef.current?.close();
  }, []);

  return useMemo(
    () => ({ messages, streamingMessage, status, outputs, meetingId, errorMessage, connectAndStart, cancel, reset }),
    [messages, streamingMessage, status, outputs, meetingId, errorMessage, connectAndStart, cancel, reset]
  );
}
