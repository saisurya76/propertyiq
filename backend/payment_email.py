"""Real, PropertyIQ-branded payment confirmation emails.

Note on Dodo's own native behavior, checked directly against Dodo's
real docs before building this: Dodo Payments already sends its own
automatic receipt email to the customer the moment a payment succeeds,
including a summary and a link to a full, tax-compliant PDF invoice —
this happens with zero code on PropertyIQ's side, and Dodo's dashboard
has its own branding settings (logo/business name) for it. Because
Dodo is the Merchant of Record, that email is legally from Dodo, not
PropertyIQ, even with a custom logo applied there. This module builds
a SEPARATE, additional confirmation email that's genuinely
PropertyIQ's own — sent through the app's existing email relay, not
Dodo's — since that's what was actually asked for. It complements
Dodo's own receipt rather than replacing it; the actual tax invoice
and payment-processor-of-record documentation is still Dodo's.
"""

from datetime import datetime, timezone
from typing import Optional

LOGO_URL = "https://app.propertyiqweb.com/favicon.svg"


def build_payment_confirmation_html(
    *,
    product_name: str,
    amount_usd: Optional[float],
    currency: str,
    payment_id: Optional[str],
    purchase_date: Optional[str] = None,
) -> str:
    """Builds the real HTML body for a payment confirmation email —
    logo, order details, payment ID, and a footer with the same legal
    links the site's own LegalFooter component uses, matching the
    user's explicit ask for "proper logo, order details along with
    paymentid etc and footer.\""""
    date_str = purchase_date or datetime.now(timezone.utc).strftime("%B %d, %Y")
    amount_str = f"{currency.upper()} {amount_usd:,.2f}" if amount_usd is not None else "—"
    payment_id_str = payment_id or "—"

    return f"""
<div style="font-family: -apple-system, 'Segoe UI', Roboto, Arial, sans-serif; max-width: 560px; margin: 0 auto; color: #14283d;">
  <div style="text-align: center; padding: 24px 0;">
    <img src="{LOGO_URL}" alt="PropertyIQ" width="48" height="46" style="display: inline-block;" />
    <div style="font-weight: 700; font-size: 18px; margin-top: 8px; color: #14283d;">PropertyIQ</div>
  </div>

  <div style="background: #f7f9fb; border: 1px solid #d6e4ec; border-radius: 12px; padding: 24px 28px;">
    <h2 style="margin: 0 0 4px; font-size: 20px; color: #14283d;">Payment confirmed</h2>
    <p style="margin: 0 0 20px; color: #5b6f7c; font-size: 14px;">Thank you for your purchase — here's your receipt.</p>

    <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
      <tr>
        <td style="padding: 8px 0; color: #5b6f7c; border-bottom: 1px solid #ebf5fb;">Item</td>
        <td style="padding: 8px 0; text-align: right; font-weight: 600; border-bottom: 1px solid #ebf5fb;">{product_name}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; color: #5b6f7c; border-bottom: 1px solid #ebf5fb;">Amount</td>
        <td style="padding: 8px 0; text-align: right; font-weight: 600; border-bottom: 1px solid #ebf5fb;">{amount_str}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; color: #5b6f7c; border-bottom: 1px solid #ebf5fb;">Date</td>
        <td style="padding: 8px 0; text-align: right; border-bottom: 1px solid #ebf5fb;">{date_str}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; color: #5b6f7c;">Payment ID</td>
        <td style="padding: 8px 0; text-align: right; font-family: monospace; font-size: 12px;">{payment_id_str}</td>
      </tr>
    </table>
  </div>

  <p style="font-size: 13px; color: #5b6f7c; margin: 20px 0;">
    A separate, official tax invoice for this payment is available from Dodo Payments (our payment processor
    and merchant of record) — check the receipt email from Dodo, or your
    <a href="https://customer.dodopayments.com/" style="color: #2e86c1;">Dodo customer portal</a>.
  </p>

  <div style="text-align: center; padding: 20px 0; border-top: 1px solid #e5e7eb; margin-top: 12px; color: #6b7280; font-size: 12px;">
    <p style="margin: 4px 0;">PropertyIQ — Independent Property Intelligence</p>
    <p style="margin: 4px 0;">© 2026 PropertyIQ</p>
    <p style="margin: 8px 0 0;">
      <a href="https://app.propertyiqweb.com/privacy-policy.html" style="color: #4b5563;">Privacy Policy</a>
      ·
      <a href="https://app.propertyiqweb.com/terms-of-service.html" style="color: #4b5563;">Terms of Service</a>
      ·
      <a href="https://app.propertyiqweb.com/refund-policy.html" style="color: #4b5563;">Refund Policy</a>
    </p>
  </div>
</div>
""".strip()
