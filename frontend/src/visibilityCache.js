// Remembers the last admin-configured visibility map in this browser so a
// returning visitor sees the right panels on first paint. Without this,
// panels an admin has hidden would briefly render (from an all-visible
// default) and then vanish once the real setting arrived. Storage can be
// blocked or throw (private windows, blocked site data), so every access is
// wrapped and the page works the same without it.
export function loadCachedVisibility(key) {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

export function saveCachedVisibility(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable — ignore */
  }
}
