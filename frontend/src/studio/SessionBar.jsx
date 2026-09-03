import { useEffect, useState } from "react";
import { getSession, clearSession, studioApi } from "./studioApi";
import ProfilePanel from "./ProfilePanel";

// Shows the user's current subscription plan next to their email — a
// real, previously-missing gap: there was nowhere on the app that
// showed a logged-in user which plan (if any) they're actually on.
// Clicking it navigates to the Studio pricing page (via onManagePlan)
// so it doubles as a lightweight "manage my plan" entry point, without
// needing a full separate profile/settings page for this alone.
function SessionBar({ onSignOut, onManagePlan }) {
  const [session, setSession] = useState(getSession());
  const [planLabel, setPlanLabel] = useState(null);
  const [showProfile, setShowProfile] = useState(false);

  useEffect(() => {
    if (!session) return;
    let cancelled = false;
    studioApi.getStatus()
      .then((result) => {
        if (cancelled) return;
        setPlanLabel(result.tier_id ? result.tier_id.replace(/_/g, " ") : "No active plan");
      })
      .catch(() => {
        if (!cancelled) setPlanLabel(null); // fails silently — this is a nice-to-have status display, not critical path
      });
    return () => { cancelled = true; };
  }, [session]);

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
      <span
        className="session-profile-icon"
        onClick={() => setShowProfile(true)}
        role="button"
        tabIndex={0}
        title="Your account"
      >
        👤
      </span>
      {planLabel && (
        <span
          className="session-plan-badge"
          onClick={onManagePlan}
          role={onManagePlan ? "button" : undefined}
          tabIndex={onManagePlan ? 0 : undefined}
          title={onManagePlan ? "Manage your subscription" : undefined}
        >
          Plan: {planLabel}
        </span>
      )}
      <span className="studio-sign-out-link" onClick={handleClick}>Sign out</span>

      {showProfile && (
        <ProfilePanel
          onClose={() => setShowProfile(false)}
          onUpgrade={() => {
            setShowProfile(false);
            if (onManagePlan) onManagePlan();
          }}
          onSignedOut={() => {
            setShowProfile(false);
            handleClick();
          }}
        />
      )}
    </div>
  );
}

export default SessionBar;
