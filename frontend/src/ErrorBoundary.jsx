import { Component } from "react";

/* This app had zero React error boundaries anywhere — confirmed by a
   direct search, not an assumption. That means any uncaught render-time
   error, from any cause, unmounts the ENTIRE app and leaves the visitor
   staring at a blank page with no way forward except guessing to
   reload. That's exactly what happened on the "Download PropertyIQ
   Report" button's Google-Translate/React DOM crash — the PDF had
   already downloaded by the time the crash hit, so the user was left
   with a blank tab despite the thing they actually wanted having
   worked.

   This doesn't replace fixing the actual crash causes (do that too) —
   it's the last line of defense for whichever one hasn't been found
   yet, so a future one degrades to a recoverable message instead of a
   blank page. */
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error("PropertyIQ crashed:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            maxWidth: "480px",
            margin: "80px auto",
            padding: "32px",
            textAlign: "center",
            fontFamily: "sans-serif",
          }}
        >
          <h2 style={{ marginBottom: "12px" }}>Something went wrong</h2>
          <p style={{ color: "#64748b", marginBottom: "24px" }}>
            This page hit an unexpected error. If you just downloaded a report or completed a
            payment, that part likely still went through — reloading is safe.
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: "12px 24px",
              borderRadius: "10px",
              border: "none",
              background: "#2c1f47",
              color: "white",
              fontWeight: "700",
              cursor: "pointer",
            }}
          >
            Reload Page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
