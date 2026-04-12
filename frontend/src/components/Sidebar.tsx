type Props = {
  meetings: Array<{ id: string; status: string }>;
  onNewMeeting: () => void;
  onOpenSettings: () => void;
};

export function Sidebar({ meetings, onNewMeeting, onOpenSettings }: Props) {
  return (
    <aside className="sidebar">
      <h2>Boardroom</h2>
      <button onClick={onNewMeeting}>New Meeting</button>
      <button className="secondary" onClick={onOpenSettings}>
        Settings
      </button>
      <div className="section-title">Recent meetings</div>
      <ul className="history-list">
        {meetings.length === 0 ? (
          <li className="muted">No meetings yet.</li>
        ) : (
          meetings.map((meeting) => (
            <li key={meeting.id}>
              <span>{meeting.id}</span>
              <small>{meeting.status}</small>
            </li>
          ))
        )}
      </ul>
    </aside>
  );
}

