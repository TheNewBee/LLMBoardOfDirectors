type Props = {
  canCancel: boolean;
  onCancel: () => void;
};

export function MeetingControls({ canCancel, onCancel }: Props) {
  return (
    <div className="controls">
      <button type="button" className="danger" onClick={onCancel} disabled={!canCancel}>
        Cancel Meeting
      </button>
    </div>
  );
}

