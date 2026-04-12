type Props = {
  status: string;
  activeSpeaker: string | null;
  turns: number;
  meetingId: string | null;
  canCancel: boolean;
  onCancel: () => void;
};

const statusLabels: Record<string, string> = {
  idle: "Idle",
  connecting: "Connecting",
  running: "Running",
  cancelling: "Cancelling",
  done: "Complete",
  error: "Error"
};

export function MeetingStatus({ status, activeSpeaker, turns, meetingId, canCancel, onCancel }: Props) {
  const normalizedStatus = status.toLowerCase();
  const statusLabel = statusLabels[normalizedStatus] ?? status;
  const speakerLabel = activeSpeaker ?? (normalizedStatus === "running" ? "Waiting" : "None");

  return (
    <header className="meeting-status-bar">
      <div className="meeting-title-block">
        <p className="eyebrow">Live Meeting</p>
        <h1 id="live-meeting-title">Boardroom process</h1>
        <p>Follow every turn as agents challenge, respond, and converge.</p>
      </div>

      <div className="meeting-status-details" aria-label="Meeting status details">
        <span className={`status-pill status-${normalizedStatus}`}>{statusLabel}</span>
        <span>
          <strong>{turns}</strong> turns
        </span>
        <span>
          Active <strong>{speakerLabel}</strong>
        </span>
        {meetingId ? (
          <span className="meeting-id">
            Meeting <code>{meetingId}</code>
          </span>
        ) : null}
      </div>

      <button type="button" className="danger" onClick={onCancel} disabled={!canCancel}>
        Cancel meeting
      </button>
    </header>
  );
}
