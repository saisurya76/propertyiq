import { useCallback, useEffect, useState } from "react";
import { API_BASE } from "../config";
import { getSession, studioApi } from "../studio/studioApi";
import { loadCachedVisibility, saveCachedVisibility } from "../visibilityCache";

const LAUNCH_MODE_CACHE_KEY = "piq_launch_mode_v1";
const MY_ACCESS_CACHE_KEY = "piq_my_access_v1";

// Quick Analysis-only launch mode, seen from the visitor's side.
//
// While the mode is on, anything tied to a Studio plan is shown only to
// people who already have access to it; everyone else doesn't see a panel
// that points at plans that can't be bought. People who DO have access see
// exactly what they saw before. This never changes an admin setting: it only
// decides, per visitor, whether a panel is worth showing.
//
// launchMode: null = not known yet (gated things wait rather than flash),
// true/false once known. A failed lookup never hides anything from someone
// who should have it: unknown mode counts as off, a failed access lookup
// counts as "has access".
export default function useLaunchGate({ enabled = true, refreshKey = null } = {}) {
  const [launchMode, setLaunchMode] = useState(() => {
    const cached = loadCachedVisibility(LAUNCH_MODE_CACHE_KEY);
    return cached && typeof cached.active === "boolean" ? cached.active : null;
  });
  const [sessionTick, setSessionTick] = useState(0);
  // Remembered from this browser's last visit (same person only), so the
  // strips they are entitled to show immediately instead of waiting for the
  // server. It is replaced by the real answer as soon as that arrives, and it
  // only ever decides whether a panel is shown, never what anyone can use.
  const [myAccess, setMyAccess] = useState(() => {
    const cached = loadCachedVisibility(MY_ACCESS_CACHE_KEY);
    const email = getSession()?.email || null;
    return cached && email && cached.email === email && Array.isArray(cached.features) ? cached : null;
  });

  useEffect(() => {
    fetch(`${API_BASE}/api/launch-mode`)
      .then((res) => res.json())
      .then((data) => {
        setLaunchMode(!!data.active);
        saveCachedVisibility(LAUNCH_MODE_CACHE_KEY, { active: !!data.active });
      })
      .catch(() => setLaunchMode((prev) => (prev === null ? false : prev)));
  }, []);

  useEffect(() => {
    const bump = () => setSessionTick((n) => n + 1);
    window.addEventListener("piq-session-changed", bump);
    return () => window.removeEventListener("piq-session-changed", bump);
  }, []);

  const sessionEmail = getSession()?.email || null;
  useEffect(() => {
    if (!enabled || !sessionEmail || launchMode === false) return;
    studioApi
      .getStatus()
      .then((st) => {
        const next = { email: sessionEmail, hasPlan: !!st.tier_id, features: st.features || [] };
        setMyAccess(next);
        saveCachedVisibility(MY_ACCESS_CACHE_KEY, next);
      })
      .catch(() => setMyAccess({ email: sessionEmail, failedOpen: true, hasPlan: true, features: [] }));
  }, [enabled, sessionEmail, launchMode, refreshKey, sessionTick]);

  // feature: a feature name the visitor's plan must include, or null for
  // "any active plan" (the Construction Studio strip).
  const canSee = useCallback(
    (feature) => {
      if (launchMode === false) return true;
      if (launchMode === null) return false;
      if (!myAccess || myAccess.email !== sessionEmail) return false;
      if (myAccess.failedOpen) return true;
      return feature === null ? myAccess.hasPlan : myAccess.features.includes(feature);
    },
    [launchMode, myAccess, sessionEmail]
  );

  return { launchMode, canSee };
}
