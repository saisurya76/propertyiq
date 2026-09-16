// The single, real source of truth for which backend this build talks
// to. Reads from Vite's own env var mechanism (VITE_API_BASE, set per
// Vercel deployment/environment) so a staging build can point at a
// staging backend without touching a single line of app code — only
// falls back to the real production URL when that env var isn't set,
// so any existing build/deployment that doesn't set it keeps working
// exactly as it always has.
export const API_BASE = import.meta.env.VITE_API_BASE || "https://propertyiq-api-q21y.onrender.com";
