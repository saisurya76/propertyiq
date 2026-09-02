// A shared footer with legal links, used across every page in the app —
// the main homepage previously had its own inline footer with no legal
// links at all, and Auth/Pricing/Designs/Construction/Admin had no
// footer whatsoever. This replaces the old inline footer and gets
// added to every one of those views, plus the two standalone pages
// (ChallengeView.jsx, NeighborhoodInsights.jsx) that render outside
// App.jsx entirely.
function LegalFooter() {
  return (
    <footer className="footer">
      <p>PropertyIQ v1.0.0 Beta</p>
      <p>Independent Property Intelligence</p>
      <p>© 2026 PropertyIQ</p>
      <p className="legal-footer-links">
        <a href="/privacy-policy.html" target="_blank" rel="noopener noreferrer">Privacy Policy</a>
        {" · "}
        <a href="/terms-of-service.html" target="_blank" rel="noopener noreferrer">Terms of Service</a>
        {" · "}
        <a href="/refund-policy.html" target="_blank" rel="noopener noreferrer">Refund Policy</a>
      </p>
    </footer>
  );
}

export default LegalFooter;
