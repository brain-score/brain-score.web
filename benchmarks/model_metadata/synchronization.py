"""Discover merged metadata PRs as data and retry trusted publication."""

from datetime import datetime, timedelta, timezone
import json
from typing import Any, Callable

from .github import ProposalError, allowed_path

STATE_KEY = "metadata-synchronization-v1"
OVERLAP = timedelta(minutes=10)
MAX_PAGES = 10


def timestamp(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.utcoffset() is None:
            raise ValueError()
        return result.astimezone(timezone.utc)
    except (ValueError, AttributeError, TypeError):
        raise ProposalError("Synchronization timestamps must include a timezone.") from None


class RedisState:
    def __init__(self, backend):
        self.client = backend.client.get_client(write=True)
        self.key = backend.make_key(STATE_KEY)
        self.client.ping()

    def read(self, domain):
        value = self.client.hget(self.key, domain)
        return json.loads(value) if value else {}

    def save(self, domain, value):
        self.client.hset(self.key, domain, json.dumps(value, sort_keys=True))


class DryRunState:
    def read(self, domain):
        return {}

    def save(self, domain, value):
        raise ProposalError("A dry run cannot save synchronization state.")


def merged_candidates(github, config, start, lower, now):
    candidates = []
    for page in range(1, MAX_PAGES + 1):
        pulls = github.request("GET", f"/repos/{config['repository']}/pulls", params={
            "state": "closed", "base": config["branch"], "sort": "updated",
            "direction": "desc", "per_page": 100, "page": page,
        })
        for pr in pulls:
            if (pr.get("merged_at") and timestamp(pr["merged_at"]) >= start
                    and timestamp(pr["merged_at"]) <= now
                    and timestamp(pr["updated_at"]) >= lower
                    and pr["base"]["ref"] == config["branch"]
                    and pr["base"]["repo"]["full_name"] == config["repository"]):
                candidates.append(pr)
        if len(pulls) < 100 or timestamp(pulls[-1]["updated_at"]) < lower:
            return sorted(candidates, key=lambda pr: (pr["merged_at"], pr["number"]))
    raise ProposalError("Synchronization exceeded 1,000 closed PRs; narrow the catch-up window.")


def sync_domain(
    domain: str,
    config: dict,
    github: Any,
    state: Any,
    start: datetime,
    now: datetime,
    publish: Callable,
    dry_run: bool = False,
) -> dict:
    """Publish new PRs and retry deferred files independently of the watermark."""
    previous = state.read(domain)
    if previous.get("start") != start.isoformat():
        previous = {}
    cursor = timestamp(previous["cursor"]) if previous.get("cursor") else start
    if cursor > now:
        raise ProposalError("Synchronization checkpoint is in the future.")
    lower = max(start, cursor - OVERLAP)
    completed = previous.get("completed", {})
    deferred = previous.get("deferred", {})
    value = {
        "start": start.isoformat(),
        "cursor": cursor.isoformat(),
        "completed": completed,
        "deferred": deferred,
    }
    result = {
        "domain": domain,
        "processed_prs": [],
        "candidate_prs": [],
        "deferred_prs": [],
        "errors": [],
    }
    candidates = {
        str(pr["number"]): pr
        for pr in merged_candidates(github, config, start, lower, now)
    }
    # A pending registration can arrive after the discovery overlap has expired.
    for key in deferred:
        if key not in candidates:
            try:
                candidates[key] = github.request(
                    "GET", f"/repos/{config['repository']}/pulls/{int(key)}"
                )
            except Exception as exc:
                result["errors"].append({"pr": int(key), "error": type(exc).__name__})
    for key, pr in sorted(
        candidates.items(), key=lambda item: (item[1]["merged_at"], int(item[0]))
    ):
        number = int(key)
        identity = pr["merge_commit_sha"]
        pending = deferred.get(key)
        if not pending and completed.get(key, {}).get("sha") == identity:
            continue
        try:
            paths = None
            if pending and pending["sha"] == identity:
                paths = [item["path"] for item in pending["files"]]
                relevant = True
            else:
                files = github.pages(
                    f"/repos/{config['repository']}/pulls/{number}/files"
                )
                relevant = any(
                    allowed_path(config, item["filename"])
                    or allowed_path(config, item.get("previous_filename", ""))
                    for item in files
                )
            if relevant:
                result["candidate_prs"].append(number)
                if dry_run:
                    if pending:
                        result["deferred_prs"].append(
                            {"pr": number, "files": pending["files"]}
                        )
                    continue
                if paths is None:
                    publications = publish(domain, number, github)
                else:
                    publications = publish(domain, number, github, paths=paths)
                result["processed_prs"].append(number)
                pending_files = [
                    {"path": item["path"], "deferred_models": item["deferred_models"]}
                    for item in publications
                    if item.get("deferred_models")
                ]
                if pending_files:
                    deferred[key] = {"sha": identity, "files": pending_files}
                    completed.pop(key, None)
                    result["deferred_prs"].append(
                        {"pr": number, "files": pending_files}
                    )
                    state.save(domain, value)
                    continue
            if not dry_run:
                deferred.pop(key, None)
                completed[key] = {"sha": identity, "updated_at": pr["updated_at"]}
                state.save(domain, value)
        except Exception as exc:
            # Do not retain token-bearing exception text or arbitrary API payloads.
            result["errors"].append({"pr": number, "error": type(exc).__name__})
    if not dry_run and not result["errors"]:
        value["cursor"] = now.isoformat()
        value["completed"] = {
            key: record
            for key, record in completed.items()
            if timestamp(record["updated_at"]) >= now - OVERLAP
        }
        state.save(domain, value)
    return result
