import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import ChallengeView from './ChallengeView.jsx'
import NeighborhoodInsights from './NeighborhoodInsights.jsx'

// The /challenge/{id} route is deliberately routed here, before App's
// own routing/URL-sync logic even initializes — App actively rewrites
// any URL it doesn't recognize as one of its own views (main/admin/a
// country code) back to "/", which would break a shared challenge link
// on first load if App itself tried to handle this path.
const challengeMatch = window.location.pathname.match(/^\/challenge\/([a-zA-Z0-9]+)\/?$/);

// /neighborhood-insights is a standalone landing page (mirroring the
// sibling AccidentIQ product's own Travel Safety page) — routed here
// for the same reason as ChallengeView above, so App's own URL-rewrite
// logic never gets a chance to redirect it back to "/".
//
// /<code>/neighborhood-insights (e.g. /th/neighborhood-insights) is
// the same page pre-set for one of the app's already-supported
// countries — reuses the exact same country-code convention as App.jsx's
// own COUNTRY_CODE_MAP (/th, /ph, /vn, /id) rather than inventing a
// separate one for this page. The bare, no-prefix path keeps defaulting
// to India, matching every existing link/share/bookmark to this page.
const bareMatch = window.location.pathname.replace(/\/$/, '') === '/neighborhood-insights';
const countryMatch = window.location.pathname.match(/^\/([a-z]{2})\/neighborhood-insights\/?$/i);
const isNeighborhoodInsights = bareMatch || !!countryMatch;
const neighborhoodInsightsCountryCode = countryMatch ? countryMatch[1].toLowerCase() : null;

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {challengeMatch ? <ChallengeView challengeId={challengeMatch[1]} />
      : isNeighborhoodInsights ? <NeighborhoodInsights countryCode={neighborhoodInsightsCountryCode} />
      : <App />}
  </StrictMode>,
)
