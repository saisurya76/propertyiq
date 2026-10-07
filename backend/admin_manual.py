"""The admin user manual. Served only by the password-gated
POST /api/admin/manual, so it is never in the public site or its JavaScript.
No secrets belong here: environment variable NAMES only, never values.

Block types: p (paragraph), ul / ol (list of strings), warn (caution box),
tip (hint box). Keep this in step with the admin screens and the policy pages
(frontend/public/terms-of-service.html, refund-policy.html)."""

MANUAL = [
    {
        "id": "start",
        "title": "1. Getting in and the basics",
        "blocks": [
            {"type": "p", "text": "The admin area is at /admin on the site (for example app.propertyiqweb.com/admin). It asks for the admin password and nothing else. There are no admin accounts or sessions: the password is checked again on every action."},
            {"type": "ul", "items": [
                "The password is the ADMIN_DASHBOARD_PASSWORD setting on the Render service (the older name PROPERTYIQ_ADMIN_PASSWORD still works if the first isn't set). Changing it means saving it in Render and letting the service redeploy.",
                "Prod and staging are separate services with separate passwords, databases and Dodo modes. Whatever you do on one never affects the other.",
                "After 10 wrong attempts in 15 minutes the login is locked for a few minutes. A correct password resets the count.",
                "The Refresh button at the top of a screen re-reads everything on that screen from the server (including live Dodo prices) and shows 'Refreshed at <time>'. Anything you typed but did not save on the tier screen is replaced by what the server holds.",
            ]},
            {"type": "warn", "text": "If you keep two admin tabs open, the one you last loaded wins when you save. Reload before editing tiers, so you never save an out-of-date screen over newer settings. (The safety monitor refuses the dangerous cases while launch mode or a wind-down is active.)"},
        ],
    },
    {
        "id": "environments",
        "title": "2. Prod, staging and Dodo modes",
        "blocks": [
            {"type": "ul", "items": [
                "Prod: app.propertyiqweb.com (Vercel) talking to the prod Render API. Uses Dodo LIVE mode. Real money.",
                "Staging: the staging Vercel preview talking to the staging Render API. Uses Dodo TEST mode. No real money.",
                "Code goes to staging first, is tested there, and reaches prod only when you say so (the main branch).",
                "Vercel's Production VITE_API_BASE must point at the prod Render URL, and the Preview one at staging. If the site shows data from the wrong place, check that first.",
                "Dodo test mode and live mode are completely separate worlds: separate API keys, products, webhooks and customers. Always check the mode toggle in the Dodo dashboard before changing anything.",
            ]},
        ],
    },
    {
        "id": "screens",
        "title": "3. Every admin screen",
        "blocks": [
            {"type": "p", "text": "The dashboard menu has these tiles. Each opens one screen and has a Back to menu button."},
            {"type": "ol", "items": [
                "Overview & Analytics: subscription counts, Quick Analysis purchases and estimated revenue, users by tier, usage per feature, tech-stack status and subscriber locations. Revenue is an estimate from our own records; Dodo is the source of truth for money.",
                "Tier Configuration: launch mode box, wind-down box, then per-tier settings (see section 4).",
                "Property URL Import, Gemini API Key: the fallback key for importing a listing from a URL. The screen only shows whether a key is set, never the key itself. Paste a new one to replace it.",
                "Loan Eligibility, Thresholds: debt-to-income, loan-to-value, age cap and minimum credit rating used for the estimates. Changes apply immediately to the public panel and to Agent Intelligence. These are rules of thumb, not a bank's decision.",
                "Neighborhood Insights, Page Sections: show or hide any section of the public Neighborhood Insights page, with no redeploy. Useful when one data source has a problem.",
                "Homepage, Free Quick-Check Panels: show or hide each homepage panel and feature strip, and edit the little sticker text on the three feature strips. Hidden panels are hidden for everyone, including subscribers (unless you are in launch mode, which blocks hiding something a subscriber's plan includes).",
                "Active Subscriptions: every subscription record with its status (see section 11).",
                "Quick Analysis Grants: every Quick Analysis purchase and who got it. Grants are permanent and tied to the email.",
                "Refunds: look up a customer's payments by email and refund one through Dodo; record a manual refund that was handled outside Dodo; see refund history (section 7).",
                "Refund Requests: requests customers submitted themselves. Approve through Dodo, approve manually, or deny; the customer is emailed each time.",
                "Reset User Quota: gives a user a fresh monthly design quota right now. Design history is never deleted. They get an email.",
            ]},
        ],
    },
    {
        "id": "tiers",
        "title": "4. Tier Configuration in detail",
        "blocks": [
            {"type": "ul", "items": [
                "The tiers are Quick Analysis (insight_addon, a one-time purchase) and Studio Starter, Pro and Unlimited (monthly subscriptions).",
                "Price is read from Dodo and cannot be edited here. To change a price, change the product in the Dodo dashboard. Checkout only sends Dodo a product ID.",
                "Quotas (designs per month, saved designs, price watches, agent clients, properties per client): blank means unlimited. For Quick Analysis, 0 is correct.",
                "Features: a checkbox per feature per tier. Ticking or unticking takes effect for existing subscribers immediately, so removing a feature takes it away from people who are paying.",
                "Availability, Coming soon: shows the tier on the pricing page but disables its button. A confirmation appears first. People who already have that plan are not affected, and their own plan still shows as Current plan. Upgrading to a Coming-soon tier is blocked too.",
                "Free for all signed-in users: a per-feature switch that opens a feature to everyone signed in without a purchase. Price Drop Alert and Agent Intelligence can't be made free because their limits come from a plan.",
                "Save Changes saves the whole tier screen in one go. Reload first if another admin tab might have changed something.",
            ]},
            {"type": "tip", "text": "To pause new sales of one plan: tick Coming soon on it and Save. Nothing else changes, and its subscribers carry on renewing."},
        ],
    },
    {
        "id": "launch",
        "title": "5. Quick Analysis-only launch mode",
        "blocks": [
            {"type": "p", "text": "One switch at the top of Tier Configuration for a launch where only Quick Analysis is for sale. It stops NEW subscriptions and nothing else. People who already have a plan keep every feature, limit and renewal."},
            {"type": "p", "text": "Switching it ON does this, together:"},
            {"type": "ul", "items": [
                "Studio Starter, Pro and Unlimited become Coming soon, so they can't be bought on any path.",
                "The property assessment becomes free for signed-in users. This is how a new user gets a report to buy Quick Analysis from.",
                "Every panel tied to a Studio plan is hidden from people who don't already have it: the Construction Studio, Agent Intelligence and AI Advisor strips, Price Drop Alert, and the Neighborhood Insights tools (area comparison, price trends, cost of living, EMI, amortization, loan eligibility). People whose plan includes them see them exactly as before.",
                "The pricing page shows a banner that new subscriptions are launching soon.",
            ]},
            {"type": "p", "text": "Switching it OFF undoes only what ON changed (tiers it closed, the free assessment if it wasn't free before), and leaves anything else you changed in the meantime alone. Your own show/hide settings are never touched by this mode."},
            {"type": "warn", "text": "A red warning inside the box means Quick Analysis couldn't actually be sold. The usual one is DODO_PRODUCT_ID_INSIGHT_ADDON not set on that service: set it to the live product ID in Render, then redeploy. The mode also refuses to switch on if Quick Analysis is Coming soon or Free."},
            {"type": "p", "text": "A customer who opened a Studio checkout before you switched ON and pays afterwards still gets their plan. Refusing would take their money and give them nothing."},
        ],
    },
    {
        "id": "safety",
        "title": "6. The safety monitor",
        "blocks": [
            {"type": "p", "text": "While launch mode is ON, or a wind-down is in progress, a safety monitor protects two promises: no new subscriptions, and nothing a subscriber is entitled to is taken away. It works in two ways."},
            {"type": "ul", "items": [
                "Guard: before every tier save or settings save it checks the change. If it would break a rule, the save is refused with a message saying why and nothing is stored.",
                "Background check: every 60 seconds it re-checks the live settings. It re-closes any Studio plan that has been reopened and re-opens the free assessment (launch mode only). Anything it can't repair is logged as an alert.",
            ]},
            {"type": "p", "text": "What the guard refuses while it is active:"},
            {"type": "ul", "items": [
                "Making a Studio plan buyable again.",
                "Marking Quick Analysis Coming soon or Free (launch mode only), which would leave nothing to buy.",
                "Turning off the free property assessment (launch mode only).",
                "Removing a feature from a plan that has active subscribers, lowering its limits (unlimited to a number counts), or changing its billing type.",
                "Hiding a homepage panel or Neighborhood Insights section that active subscribers' plans include.",
            ]},
            {"type": "p", "text": "Always allowed: price changes, edits to a plan with no subscribers, raising limits, and switching launch mode OFF. If you truly need to do a refused thing, switch the mode off first. Every refusal, repair and alert is listed under Safety monitor log in the launch mode box."},
        ],
    },
    {
        "id": "refunds",
        "title": "7. Refunds",
        "blocks": [
            {"type": "p", "text": "What the Refund Policy promises customers (keep your decisions consistent with it):"},
            {"type": "ul", "items": [
                "Reports and Quick Analysis: refundable for a technical failure to deliver or a duplicate charge, requested within 14 days.",
                "Studio subscriptions: a full refund of the first payment if asked within 7 days of the first charge, once per customer. Renewals are not refunded; cancelling stops the next one and access continues to the end of the paid period.",
                "Billing errors (duplicate charge, charge after cancelling, charge not matching the plan): always refunded in full, no time limit.",
                "Approved refunds go back to the original payment method through Dodo and take 5 to 10 business days to appear.",
            ]},
            {"type": "p", "text": "Doing a refund in the admin:"},
            {"type": "ol", "items": [
                "Refunds screen, Look up payments: enter the customer's email. Their subscription payments are fetched from Dodo.",
                "Pick the payment and issue the refund. By default this also cancels their subscription immediately, because refunding a subscription charge while leaving it active would let them keep using the product.",
                "For a one-time purchase there is no subscription to look up: paste the payment ID from the Dodo dashboard into the manual section instead.",
                "If a customer wrote in themselves, use Refund Requests: approve through Dodo (does it for you) or approve manually (a record only), or deny. They are emailed each time.",
            ]},
            {"type": "warn", "text": "Dodo takes refunds out of your Dodo wallet balance. If it is too low Dodo answers 409 INSUFFICIENT_WALLET_FUNDS and the refund is not made. Add funds in the Dodo dashboard and try again. A manual refund only records something you did outside Dodo; it moves no money."},
        ],
    },
    {
        "id": "winddown",
        "title": "8. Taking the site down: wind-down",
        "blocks": [
            {"type": "p", "text": "Tier Configuration, Wind down subscriptions. Use it when you must stop all future renewals. It calls Dodo for every active subscriber in batches, emails each customer, and shows progress. Nothing is ever deleted: users, subscriptions, designs and reports all stay."},
            {"type": "p", "text": "Pick one of two modes:"},
            {"type": "ul", "items": [
                "Planned pause (recommended): each subscription is set not to renew on Dodo. Customers keep access until the end of the period they paid for and are not charged again. No refunds, which matches Terms section 9.1 and Refund Policy section 6.",
                "Immediate closure: for shutting down today. Each customer's latest payment is refunded in full, then the subscription is cancelled at once. Quick Analysis is closed too. You need enough in the Dodo wallet first. If a refund fails, that customer stays active and shows as failed; fix the cause and retry. It can't start while launch mode is on: switch that off first.",
            ]},
            {"type": "p", "text": "How to run it:"},
            {"type": "ol", "items": [
                "Choose the mode, write an optional note (it goes into every customer email and the site banner), type WIND DOWN, press Start. This closes all subscription plans to new buyers and lists every active subscriber as pending. It does not touch Dodo yet.",
                "Press Run all pending. It works 10 at a time with a short pause so Dodo's rate limits are respected. Each customer gets one email when their cancellation succeeds.",
                "Watch the table: status, access-until date, refund, emailed yes/no, and the exact problem for any that failed. Press Retry failed after fixing the cause. Retrying never double-cancels or double-refunds.",
                "A banner on the site tells visitors that subscriptions are paused or closed, with your note.",
                "Cross-check against the Dodo dashboard (Subscriptions, filtered by status or scheduled cancellation) and the webhook event log: each cancellation should show subscription.cancelled when its period ends.",
            ]},
            {"type": "p", "text": "If the site comes back later:"},
            {"type": "ul", "items": [
                "Before customers' paid periods end: press Resume all (planned pause only). Their non-renewal is cancelled on Dodo, their plan simply continues, and they are emailed.",
                "After a subscription has ended (or after an immediate closure): it does not restart. The customer subscribes again from the pricing page.",
                "Press Reopen plans to end the wind-down. It reopens only the plans the wind-down closed and removes the banner. The history table is kept.",
            ]},
            {"type": "tip", "text": "Do a trial first on staging, or on prod with a single test subscriber, before running it on everyone."},
        ],
    },
    {
        "id": "dodo",
        "title": "9. The Dodo dashboard: where things are",
        "blocks": [
            {"type": "ul", "items": [
                "Mode toggle (Test or Live): top of the dashboard. Check it before every change.",
                "API keys: Developer, API Keys. The key needs write access. It goes in Render as DODO_PAYMENTS_API_KEY. A 401 Unauthorized from checkout means the key and DODO_PAYMENTS_ENVIRONMENT (test_mode or live_mode) don't match.",
                "Webhooks: Developer, Webhooks. The endpoint must point at the matching Render service's /api/webhooks/dodo and subscribe to: subscription.active, updated, renewed, cancelled, failed; payment.succeeded, failed; refund.succeeded, failed. Its signing secret (starts whsec_) goes in Render as DODO_PAYMENTS_WEBHOOK_KEY.",
                "Webhook log: open the endpoint to see each delivery and its response. A failed delivery can be resent from there. This is the first place to look when a customer paid but shows no plan.",
                "Products: each plan's product ID goes in Render as DODO_PRODUCT_ID_STUDIO_STARTER, DODO_PRODUCT_ID_STUDIO_PRO, DODO_PRODUCT_ID_STUDIO_UNLIMITED and DODO_PRODUCT_ID_INSIGHT_ADDON. The report product is DODO_REPORT_PRODUCT_ID.",
                "Subscriptions and Payments: look up a customer, a subscription ID (sub_...) or a payment ID (pay_...). Refunds and the wallet balance are also here.",
            ]},
        ],
    },
    {
        "id": "env",
        "title": "10. Environment settings checklist (names only)",
        "blocks": [
            {"type": "p", "text": "Set on each Render service (prod and staging separately). The values are secrets: never paste them into chat, email or this page."},
            {"type": "ul", "items": [
                "Core: DATABASE_URL (Neon), ADMIN_DASHBOARD_PASSWORD, PROPERTYIQ_FRONTEND_URL.",
                "Payments: DODO_PAYMENTS_API_KEY, DODO_PAYMENTS_ENVIRONMENT, DODO_PAYMENTS_WEBHOOK_KEY, DODO_PRODUCT_ID_STUDIO_STARTER, DODO_PRODUCT_ID_STUDIO_PRO, DODO_PRODUCT_ID_STUDIO_UNLIMITED, DODO_PRODUCT_ID_INSIGHT_ADDON, DODO_REPORT_PRODUCT_ID.",
                "Email (login codes and notices): RESEND_API_KEY and RESEND_FROM_EMAIL (for example PropertyIQWeb <noreply@propertyiqweb.com>). If codes stop arriving, check these first and the Render logs for a relay error.",
                "Data and AI: GEMINI_API_KEY (also settable in the admin), TAVILY_API_KEY, FRED_API_KEY, LOCATIONIQ_API_KEY, OPENWEATHER_API_KEY.",
                "Shared sign-in: LIVINGIQ_AUTH_BASE_URL, INTERNAL_APP_API_KEY.",
            ]},
            {"type": "warn", "text": "PROPERTYIQ_BETA_BYPASS_PAYMENTS must NOT be true on prod. It skips payment and activates plans for free. The safety monitor logs an alert if it is on while launch mode or a wind-down is active."},
        ],
    },
    {
        "id": "statuses",
        "title": "11. What the statuses mean",
        "blocks": [
            {"type": "ul", "items": [
                "active: paying and entitled to the plan.",
                "pending_payment: the customer opened checkout but Dodo has not confirmed payment. It is not a plan and gives no access. It is only written for people without an active plan.",
                "payment_failed: a renewal failed or Dodo put the subscription on hold. No access until it is paid.",
                "cancelled: ended. Access is gone.",
                "A subscription set not to renew stays active until the period ends, then Dodo ends it and it becomes cancelled.",
                "Wind-down rows: pending (not done yet), scheduled (set not to renew), cancelled (ended now), failed (read the problem text and retry), resumed (non-renewal undone), skipped (no longer active when its turn came).",
            ]},
        ],
    },
    {
        "id": "runbook",
        "title": "12. When something goes wrong",
        "blocks": [
            {"type": "p", "text": "A customer paid but sees no active plan:"},
            {"type": "ol", "items": [
                "Active Subscriptions: find their email. pending_payment means the confirmation hasn't reached us.",
                "Dodo, Developer, Webhooks, the endpoint's log: look for subscription.active or payment.succeeded for them. If a delivery failed, resend it. Plans are activated from the checkout's own metadata, so a resend fixes it.",
                "If the webhook was never created or points at the wrong service, fix the endpoint and resend. A wrong signing secret shows as failed deliveries.",
                "Only if all that fails, ask for a manual activation to be done in the database, and note it.",
            ]},
            {"type": "p", "text": "Other common cases:"},
            {"type": "ul", "items": [
                "Login code not arriving: see the Email settings in section 10; check spam; check the Render logs.",
                "Checkout returns 500 or 'Something went wrong': usually Dodo's API key or mode mismatch, or a product ID missing for that plan.",
                "A hidden panel flashes on the page before disappearing: browsers remember the last setting. A hard refresh fixes a stale one.",
                "A customer's quota was used up by a bug: Reset User Quota.",
                "Admin login says too many attempts: wait about 15 minutes.",
                "The admin shows old numbers: press Refresh and look for the 'Refreshed at' line; if it shows an error instead, read it, then reload the page.",
            ]},
        ],
    },
    {
        "id": "policies",
        "title": "13. The policy pages",
        "blocks": [
            {"type": "ul", "items": [
                "Public pages: /terms-of-service.html, /refund-policy.html and /privacy-policy.html. They are plain files in the site's public folder and every customer email links to them.",
                "Terms section 9.1 (pausing or closing the service) and Refund Policy section 6 describe the same rules the wind-down follows. If you change how a wind-down works, change both pages and the customer emails together, or they will contradict each other.",
                "Customers are told: a planned pause means no further charges and access to the end of the paid period; an immediate closure means a full refund of the latest payment; data is never deleted because of a pause; a subscription that has ended must be bought again.",
                "Update the 'Last updated' date at the top of a page whenever its text changes.",
            ]},
        ],
    },
]


# The "find a fix fast" row at the top of the page: (what the admin is trying
# to do, chapter id). Every target must be a real chapter id (tested).
QUICK = [
    {"label": "A customer paid but has no plan", "target": "runbook"},
    {"label": "Issue a refund", "target": "refunds"},
    {"label": "Stop new subscriptions", "target": "launch"},
    {"label": "Take the site down", "target": "winddown"},
    {"label": "Change a plan, price or limit", "target": "tiers"},
    {"label": "Login codes aren't arriving", "target": "env"},
]
