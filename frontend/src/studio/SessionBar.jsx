import { getSession } from "./studioApi";

function SessionBar({ onSignOut }) {
  const session = getSession();
  if (!session) return null;

  return (
    <div className="session-bar">
      Signed in as <strong>{session.email}</strong>
      <span className="studio-sign-out-link" onClick={onSignOut}>Sign out</span>
    </div>
  );
}

export default SessionBar;
