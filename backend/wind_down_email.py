"""Customer emails for a service wind-down. Wording follows the Terms of
Service (section 9.1) and the Refund Policy (section 6); change them
together."""

from typing import Optional

LOGO_URL = "https://app.propertyiqweb.com/favicon.svg"
SITE = "https://app.propertyiqweb.com"
SUPPORT = "heliosbuildsweb@gmail.com"

_FOOTER = f"""
  <div style="text-align:center;padding:20px 0;border-top:1px solid #e5e7eb;margin-top:12px;color:#6b7280;font-size:12px;">
    <p style="margin:4px 0;">PropertyIQWeb — Independent Property Intelligence</p>
    <p style="margin:8px 0 0;">
      <a href="{SITE}/privacy-policy.html" style="color:#4b5563;">Privacy Policy</a> ·
      <a href="{SITE}/terms-of-service.html" style="color:#4b5563;">Terms of Service</a> ·
      <a href="{SITE}/refund-policy.html" style="color:#4b5563;">Refund Policy</a>
    </p>
  </div>"""


def _wrap(title: str, body_html: str) -> str:
    return f"""
<div style="font-family:-apple-system,'Segoe UI',Roboto,Arial,sans-serif;max-width:560px;margin:0 auto;color:#14283d;">
  <div style="text-align:center;padding:24px 0;">
    <img src="{LOGO_URL}" alt="PropertyIQWeb" width="48" height="46" />
    <div style="font-weight:700;font-size:18px;margin-top:8px;">PropertyIQWeb</div>
  </div>
  <div style="background:#f7f9fb;border:1px solid #d6e4ec;border-radius:12px;padding:24px 28px;font-size:14px;line-height:1.55;">
    <h2 style="margin:0 0 12px;font-size:20px;">{title}</h2>
    {body_html}
  </div>{_FOOTER}
</div>""".strip()


def _note(message: Optional[str]) -> str:
    return f"<p><em>{message}</em></p>" if message and message.strip() else ""


def _terms_line(section: str) -> str:
    return (
        f'<p style="font-size:13px;color:#5b6f7c;">This is done under {section} of our '
        f'<a href="{SITE}/terms-of-service.html">Terms of Service</a> and our '
        f'<a href="{SITE}/refund-policy.html">Refund Policy</a>. Your account, saved designs and other data '
        f'are <strong>not deleted</strong>. Questions: <a href="mailto:{SUPPORT}">{SUPPORT}</a>.</p>'
    )


def period_end_subject() -> str:
    return "Your PropertyIQWeb subscription will not renew"


def build_period_end_email(*, plan: str, access_until: Optional[str], message: Optional[str]) -> str:
    until = f"until <strong>{access_until}</strong>" if access_until else "until the end of your current billing period"
    return _wrap(
        "Your subscription will not renew",
        f"<p>We are pausing PropertyIQWeb subscriptions, so your <strong>{plan}</strong> plan has been set "
        f"<strong>not to renew</strong>. You will not be charged again.</p>"
        f"<p>You keep full access to your plan {until}. The current period is not refunded, as it is already "
        f"delivered and covered by our refund policy.</p>"
        f"<p>If the service returns, we will email you. If you wish to continue then, you can subscribe again "
        f"from the pricing page.</p>{_note(message)}{_terms_line('section 9.1')}",
    )


def immediate_subject() -> str:
    return "PropertyIQWeb subscription ended and refunded"


def build_immediate_email(*, plan: str, refund_text: Optional[str], message: Optional[str]) -> str:
    refund = (
        f"<p>We have refunded your latest payment in full (<strong>{refund_text}</strong>) to your original "
        f"payment method through Dodo Payments. It usually appears within 5-10 business days.</p>"
        if refund_text
        else "<p>We are processing a refund of your latest payment to your original payment method.</p>"
    )
    return _wrap(
        "Your subscription has ended",
        f"<p>We have had to close PropertyIQWeb with immediate effect, so your <strong>{plan}</strong> "
        f"subscription has been <strong>cancelled today</strong>. You will not be charged again.</p>"
        f"{refund}{_note(message)}{_terms_line('section 9.1')}",
    )


def resumed_subject() -> str:
    return "Good news: your PropertyIQWeb subscription continues"


def build_resumed_email(*, plan: str) -> str:
    return _wrap(
        "Your subscription continues",
        f"<p>PropertyIQWeb is continuing, so we have <strong>cancelled the non-renewal</strong> on your "
        f"<strong>{plan}</strong> plan. It will renew as normal on your next billing date and nothing changes "
        f"for you. You can still cancel any time from your profile.</p>{_terms_line('section 9.1')}",
    )
