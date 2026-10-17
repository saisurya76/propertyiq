"""Admin control for the Instagram marketing queue.

The queue lives in the public repo saisurya76/propertyiq-marketing
(posts/queue.json). A GitHub Action there sends *approved* posts to
Buffer. This module lets the admin dashboard list the queue, approve or
un-approve a post with a send time, and trigger the job — through
GitHub's API, with a token that only exists in this server's env.

It deliberately can't touch posts Buffer already holds (queued/sent) and
never publishes anything itself.
"""
import base64
import json
import os
from datetime import datetime, timezone

import requests

REPO = os.getenv("MARKETING_REPO", "saisurya76/propertyiq-marketing")
QUEUE_PATH = "posts/queue.json"
WORKFLOW = "publish.yml"
EDITABLE = {"draft", "approved"}
MODES = {"send", "dry-run", "channels"}
# Buffer's free plan holds 10 queued posts per channel.
MAX_APPROVED_PLUS_QUEUED = 8


class MarketingError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _token() -> str:
    t = os.getenv("MARKETING_GITHUB_TOKEN", "").strip()
    if not t:
        raise MarketingError(503, "Marketing is not connected: MARKETING_GITHUB_TOKEN is not set on the server.")
    return t


def _headers():
    return {"Authorization": f"Bearer {_token()}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def _gh(method: str, path: str, **kw):
    try:
        r = requests.request(method, f"https://api.github.com/repos/{REPO}/{path}",
                             headers=_headers(), timeout=20, **kw)
    except requests.RequestException as e:
        raise MarketingError(502, f"Could not reach GitHub: {e.__class__.__name__}")
    return r


def load_queue():
    r = _gh("GET", f"contents/{QUEUE_PATH}")
    if r.status_code in (401, 403, 404):
        raise MarketingError(502, "GitHub refused the marketing token (check its repo access and expiry).")
    if not r.ok:
        raise MarketingError(502, f"GitHub error {r.status_code} reading the queue.")
    body = r.json()
    posts = json.loads(base64.b64decode(body["content"]).decode())
    return posts, body["sha"]


def _save(posts, sha, message):
    payload = {"message": message, "sha": sha,
               "content": base64.b64encode((json.dumps(posts, indent=1) + "\n").encode()).decode()}
    return _gh("PUT", f"contents/{QUEUE_PATH}", json=payload)


def _parse_future(value: str) -> str:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise MarketingError(400, "Send time is not a valid date and time.")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    if dt <= datetime.now(timezone.utc):
        raise MarketingError(400, "Send time must be in the future.")
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def apply_update(posts, post_id, status, scheduled_at):
    """Pure edit of the list; raises MarketingError on any invalid change."""
    post = next((p for p in posts if p.get("id") == post_id), None)
    if post is None:
        raise MarketingError(404, "Post not found.")
    if post.get("status") not in EDITABLE:
        raise MarketingError(409, "This post is already with Buffer and can't be changed here.")
    if status not in EDITABLE:
        raise MarketingError(400, "Status must be draft or approved.")
    if status == "approved":
        if not scheduled_at:
            raise MarketingError(400, "Pick a send time before approving.")
        others = sum(1 for p in posts if p.get("id") != post_id and (p.get("status") == "queued" or p.get("status") == "approved"))
        if others >= MAX_APPROVED_PLUS_QUEUED:
            raise MarketingError(409, f"Buffer's free plan holds 10 queued posts; this keeps a safe limit of {MAX_APPROVED_PLUS_QUEUED}.")
        post["scheduled_at"] = _parse_future(scheduled_at)
        post.pop("error", None)
    else:
        post["scheduled_at"] = _parse_future(scheduled_at) if scheduled_at else post.get("scheduled_at")
    post["status"] = status
    return post


def list_posts():
    posts, _ = load_queue()
    return posts


def update_post(post_id, status, scheduled_at):
    for _ in range(2):  # the Action may write the file between our read and write
        posts, sha = load_queue()
        post = apply_update(posts, post_id, status, scheduled_at)
        r = _save(posts, sha, f"Admin: {status} {post_id}")
        if r.status_code in (409, 422):
            continue
        if not r.ok:
            raise MarketingError(502, f"GitHub error {r.status_code} saving the change.")
        return post
    raise MarketingError(409, "The queue changed while saving. Refresh and try again.")


def run_job(mode):
    if mode not in MODES:
        raise MarketingError(400, "Unknown mode.")
    r = _gh("POST", f"actions/workflows/{WORKFLOW}/dispatches", json={"ref": "main", "inputs": {"mode": mode}})
    if r.status_code == 204:
        return {"status": "started", "mode": mode,
                "url": f"https://github.com/{REPO}/actions/workflows/{WORKFLOW}"}
    if r.status_code in (401, 403, 404):
        raise MarketingError(502, "GitHub refused to start the job (the token needs Actions: write).")
    raise MarketingError(502, f"GitHub error {r.status_code} starting the job.")
