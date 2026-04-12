type Props = {
  meetings: Array<{ id: string; status: string }>;
  onNewMeeting: () => void;
  onOpenSettings: () => void;
};

export function Sidebar({ meetings, onNewMeeting, onOpenSettings }: Props) {
  return (
    <aside className="sidebar">
      <div className="brand-lockup">
        <span className="brand-mark" aria-hidden="true">
          B
        </span>
        <div>
          <h2>Boardroom</h2>
          <p>Adversarial AI meetings</p>
        </div>
      </div>

      <div className="sidebar-actions">
        <button type="button" onClick={onNewMeeting}>
          New meeting
        </button>
        <button type="button" className="secondary" onClick={onOpenSettings}>
          Settings
        </button>
      </div>

      <div className="section-title">Recent meetings</div>
      <ul className="history-list">
        {meetings.length === 0 ? (
          <li className="muted">No meetings yet.</li>
        ) : (
          meetings.map((meeting) => (
            <li className="history-item" key={meeting.id}>
              <span>{meeting.id}</span>
              <small>{meeting.status}</small>
            </li>
          ))
        )}
      </ul>
    </aside>
  );
}
