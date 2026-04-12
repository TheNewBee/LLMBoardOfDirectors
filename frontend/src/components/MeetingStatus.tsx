type Props = {
  status: string;
  activeSpeaker: string | null;
  turns: number;
};

export function MeetingStatus({ status, activeSpeaker, turns }: Props) {
  return (
    <div className="status-row">
      <strong>Status:</strong> <span>{status}</span>
      <strong>Turns:</strong> <span>{turns}</span>
      <strong>Active:</strong> <span>{activeSpeaker ?? "None"}</span>
    </div>
  );
}

