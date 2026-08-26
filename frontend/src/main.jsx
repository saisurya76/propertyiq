import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import ChallengeView from './ChallengeView.jsx'

// The /challenge/{id} route is deliberately routed here, before App's
// own routing/URL-sync logic even initializes — App actively rewrites
// any URL it doesn't recognize as one of its own views (main/admin/a
// country code) back to "/", which would break a shared challenge link
// on first load if App itself tried to handle this path.
const challengeMatch = window.location.pathname.match(/^\/challenge\/([a-zA-Z0-9]+)\/?$/);

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {challengeMatch ? <ChallengeView challengeId={challengeMatch[1]} /> : <App />}
  </StrictMode>,
)
