import os
from typing import Optional

import requests
from fastapi import Header, HTTPException

from backend.auth_store import get_session_email

# Preferred path: livingiq-auth's centralized Resend relay (already live and
# configured — see livingiq-auth/server/lib/emailClient.js + routes/notifications.js).
# Falls back to a direct Resend call only if these aren't set, so this never
# breaks an environment that isn't wired to livingiq-auth yet.
LIVINGIQ_AUTH_BASE_URL = os.getenv("LIVINGIQ_AUTH_BASE_URL", "").rstrip("/")
INTERNAL_APP_API_KEY = os.getenv("INTERNAL_APP_API_KEY", "")

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "PropertyIQ <noreply@propertyiqweb.com>")


def send_email(to_email: str, subject: str, html: str) -> bool:
    """Generic email sender, extracted from send_otp_email so other
    features (price-drop alerts) can send email through the same
    livingiq-auth-relay-first, direct-Resend-fallback path without
    duplicating that logic. send_otp_email is rebuilt on top of this
    with byte-for-byte identical request bodies/behavior to before this
    extraction — this is a pure refactor, not a behavior change."""
    if LIVINGIQ_AUTH_BASE_URL and INTERNAL_APP_API_KEY:
        response = requests.post(
            f"{LIVINGIQ_AUTH_BASE_URL}/api/notifications/email",
            headers={"x-internal-api-key": INTERNAL_APP_API_KEY},
            json={"to": to_email, "subject": subject, "html": html},
            timeout=10,
        )
        return response.status_code < 300

    if RESEND_API_KEY:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={"from": RESEND_FROM_EMAIL, "to": [to_email], "subject": subject, "html": html},
            timeout=10,
        )
        return response.status_code < 300

    raise HTTPException(
        status_code=503,
        detail="Email sending is not configured. Set LIVINGIQ_AUTH_BASE_URL + INTERNAL_APP_API_KEY "
               "(preferred, uses livingiq-auth's centralized Resend) or RESEND_API_KEY directly."
    )


def send_otp_email(to_email: str, code: str, purpose: str = "sign_in") -> bool:
    """Send the OTP code. Tries livingiq-auth's centralized Resend relay
    first (POST /api/notifications/email, x-internal-api-key auth — same
    contract DealIQ/AccidentIQ already use). Falls back to a direct Resend
    call if LIVINGIQ_AUTH_BASE_URL/INTERNAL_APP_API_KEY aren't set. Raises
    a clear HTTPException if neither path is configured.

    `purpose` selects the email copy — "sign_in" (default) or
    "unlock_design" (used when re-verifying a user before letting them
    unlock a locked property; deliberately distinct wording so the person
    understands why they're getting a second code even though they're
    already signed in)."""

    if purpose == "unlock_design":
        subject = "Confirm unlocking your PropertyIQ design"
        html = (
            f"<p>Someone requested to unlock a locked PropertyIQ design on your account. "
            f"Enter this code to confirm:</p>"
            f"<h2>{code}</h2>"
            f"<p>This code expires in 10 minutes. If you didn't request this, your design stays locked "
            f"and you can ignore this email.</p>"
        )
    else:
        subject = "Your PropertyIQ verification code"
        html = (
            f"<p>Your PropertyIQ verification code is:</p>"
            f"<h2>{code}</h2>"
            f"<p>This code expires in 10 minutes. If you didn't request this, you can ignore this email.</p>"
        )

    return send_email(to_email, subject, html)


def get_current_user_email(authorization: Optional[str] = Header(None)) -> str:
    """FastAPI dependency: requires a valid 'Bearer <session_token>' header,
    returns the associated verified email or raises 401."""

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    email = get_session_email(token)

    if email is None:
        raise HTTPException(status_code=401, detail="Session expired or invalid. Please sign in again.")

    return email


def get_current_user_email_optional(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """Same real session lookup as get_current_user_email, for the one
    real case that needs it: an endpoint usable both signed-out (e.g.
    turning OFF a comparison's monitoring, never paywalled) and
    signed-in with an entitlement check the caller applies itself (e.g.
    turning monitoring ON). Returns None rather than raising 401 for a
    missing/invalid/expired session — the caller decides what None
    means for its own action, this dependency just doesn't force every
    caller to be logged in to use the endpoint at all."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    return get_session_email(token)
