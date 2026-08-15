import { useState } from "react";
import { getSession, clearSession } from "./studioApi";

function StudioTopBar({ onBackToReport, onSignOut }) {
  const [session, setSession] = useState(getSession());

  const handleSignOutClick = () => {
    clearSession();
    setSession(null);
    if (onSignOut) onSignOut();
  };

  return (
    <div className="studio-top-bar">
      <span className="studio-prominent-link" onClick={onBackToReport}>
        ← Back to your report
      </span>
      {session && (
        <span className="studio-top-bar-session">
          Signed in as <strong>{session.email}</strong>
          <span className="studio-sign-out-link" onClick={handleSignOutClick}>Sign out</span>
        </span>
      )}
    </div>
  );
}

export default StudioTopBar;
