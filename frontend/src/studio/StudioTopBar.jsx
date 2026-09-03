import { useState } from "react";
import { getSession, clearSession } from "./studioApi";

function StudioTopBar({ onBackToReport, onSignOut, onManagePlan }) {
  const [session, setSession] = useState(getSession());

  const handleSignOutClick = () => {
    clearSession();
    setSession(null);
    if (onSignOut) onSignOut();
  };

  return (
    <header className="studio-header">
      <div className="studio-header-brand">
        <span className="studio-header-logo">PROPERTYIQ</span>
        <span className="studio-header-divider" />
        <span className="studio-header-product">Studio</span>
      </div>

      <div className="studio-header-actions">
        <span className="studio-prominent-link" onClick={onBackToReport}>
          ← Back to your report
        </span>
        {onManagePlan && (
          <span className="studio-prominent-link" onClick={onManagePlan}>
            Plans &amp; Pricing
          </span>
        )}
        {session && (
          <span className="studio-top-bar-session">
            <strong>{session.email}</strong>
            <span className="studio-sign-out-link" onClick={handleSignOutClick}>Sign out</span>
          </span>
        )}
      </div>
    </header>
  );
}

export default StudioTopBar;
