import os
from typing import Optional

import requests
from fastapi import Header, HTTPException

from backend.auth_store import get_session_email

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "PropertyIQ <noreply@propertyiqweb.com>")


def send_otp_email(to_email: str, code: str) -> bool:
    """Send the OTP code via Resend. Returns True if the send request was
    accepted (2xx). Requires RESEND_API_KEY to be set; raises a clear
    HTTPException if not configured, matching the get_dodo_client() pattern
    already used elsewhere in this codebase for missing config."""

    if not RESEND_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Email sending is not configured. Set RESEND_API_KEY."
        )

    response = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
        json={
            "from": RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": "Your PropertyIQ verification code",
            "html": (
                f"<p>Your PropertyIQ verification code is:</p>"
                f"<h2>{code}</h2>"
                f"<p>This code expires in 10 minutes. If you didn't request this, you can ignore this email.</p>"
            ),
        },
        timeout=10,
    )

    return response.status_code < 300


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
