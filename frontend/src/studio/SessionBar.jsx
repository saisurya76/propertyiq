import { useState } from "react";
import { getSession, clearSession } from "./studioApi";

function SessionBar({ onSignOut }) {
  const [session, setSession] = useState(getSession());
  if (!session) return null;

  const handleClick = () => {
    clearSession();
    setSession(null); // guarantees a re-render even if the parent's own
                       // state doesn't change (e.g. already on "main")
    if (onSignOut) onSignOut();
  };

  return (
    <div className="session-bar">
      Signed in as <strong>{session.email}</strong>
      <span className="studio-sign-out-link" onClick={handleClick}>Sign out</span>
    </div>
  );
}

export default SessionBar;
