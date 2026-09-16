"""A real, simple rate limiter for this app's genuinely brute-forceable
endpoints — the OTP code (a 6-digit, 10-minute-lived secret with no
prior rate limiting at all) and the single shared admin dashboard
password (checked independently on every one of its ~15 endpoints,
with no session/lockout concept).

Deliberately in-memory, not database-backed: this app runs as a single
Render backend instance today, and a database round-trip on every auth
attempt would add real latency for a check that only needs to survive
until the next deploy restart, not persist forever. This IS a real,
known limitation worth remembering if this app is ever scaled to
multiple instances — an in-memory counter doesn't share state across
them, so it should be swapped for a shared store (e.g. a real
`rate_limit_attempts` Postgres table, matching this codebase's own
established pattern of using Postgres for everything else) at that
point, not before.

Keyed by whatever the caller considers the real, fixed target of the
attack — an email for OTP requests (so rotating IPs doesn't help an
attacker targeting one victim), or a single fixed string for the admin
password (since it's one shared secret, not per-user, so an IP-based
limit could be trivially bypassed by rotating IPs — a global attempt
counter can't be)."""

import time
from collections import defaultdict, deque

# key -> deque of attempt timestamps within the current window. A
# plain dict of deques, not a specialized cache library — simple
# enough that adding a real dependency wasn't worth it.
_attempts: dict[str, deque] = defaultdict(deque)


def check_rate_limit(key: str, *, max_attempts: int, window_seconds: int) -> bool:
    """Records this attempt and returns whether it's allowed. Old
    attempts outside the window are pruned on every call rather than
    on a timer, so memory never grows unbounded for a key that stops
    being hit."""
    now = time.monotonic()
    window = _attempts[key]
    while window and now - window[0] > window_seconds:
        window.popleft()

    if len(window) >= max_attempts:
        return False

    window.append(now)
    return True


def reset_rate_limit(key: str) -> None:
    """Clears a key's attempt history — used after a genuinely
    successful auth, so a legitimate user's own next few actions
    aren't needlessly throttled by attempts that already succeeded."""
    _attempts.pop(key, None)
