import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { MeetingEvent } from "../types";

type StartPayload = {
  briefing: { text: string; objectives: string[] };
  agents: string[];
  models_by_agent?: Record<string, string>;
  enable_web_search?: boolean;
};

export function useMeetingSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const [events, setEvents] = useState<MeetingEvent[]>([]);
  const [status, setStatus] = useState("idle");

  const connectAndStart = useCallback((payload: StartPayload) => {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/meeting`);
    wsRef.current = ws;
    setStatus("connecting");

    ws.onopen = () => {
      setStatus("running");
      ws.send(JSON.stringify({ type: "start_meeting", ...payload }));
    };

    ws.onmessage = (message) => {
      const parsed = JSON.parse(message.data) as MeetingEvent;
      setEvents((prev) => [...prev, parsed]);
      if (
        parsed.type === "meeting_complete" ||
        parsed.type === "meeting_cancelled" ||
        parsed.type === "error"
      ) {
        setStatus(parsed.type === "error" ? "error" : "done");
      }
    };

    ws.onerror = () => setStatus("error");
  }, []);

  const cancel = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "cancel" }));
      setStatus("cancelling");
    }
  }, []);

  const reset = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    setEvents([]);
    setStatus("idle");
  }, []);

  useEffect(() => {
    return () => wsRef.current?.close();
  }, []);

  return useMemo(
    () => ({ events, status, connectAndStart, cancel, reset }),
    [events, status, connectAndStart, cancel, reset]
  );
}

