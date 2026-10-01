"""GitHub API boundary. Repository targets come from server configuration."""

import base64
import hashlib
import re
import time
import threading
from django.core.cache import cache
from urllib.parse import quote
import requests
from django.conf import settings


class ProposalError(ValueError):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def domains():
    return getattr(settings, "MODEL_METADATA_REPOSITORIES", {})


def target(domain):
    config = domains().get(domain)
    if not config:
        raise ProposalError("Metadata editing is not configured for this domain.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", config["repository"]):
        raise ProposalError("Invalid repository configuration.")
    return config


def allowed_path(config, path):
    root = config["model_root"].strip("/") + "/"
    return (
        path.startswith(root)
        and path.rsplit("/", 1)[-1] in {"metadata.yaml", "metadata.yml"}
        and len(path[len(root) :].split("/")) == 2
        and ".." not in path.split("/")
    )


def configured():
    import importlib.util

    return bool(
        importlib.util.find_spec("brainscore_metadata")
        and getattr(settings, "MODEL_METADATA_EDIT_ENABLED", False)
        and getattr(settings, "METADATA_GITHUB_CLIENT_ID", "")
        and getattr(settings, "METADATA_GITHUB_CLIENT_SECRET", "")
        and getattr(settings, "METADATA_GITHUB_APP_ID", "")
        and getattr(settings, "METADATA_GITHUB_APP_PRIVATE_KEY", "")
        and getattr(settings, "METADATA_GITHUB_CALLBACK_URL", "")
    )


class GitHub:
    _read_tokens = {}
    _token_lock = threading.Lock()

    def __init__(self, token=None, *, read_only=False):
        self.read_only = read_only
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )
        if token:
            self.session.headers["Authorization"] = "Bearer " + token

    @classmethod
    def installation(cls, config, *, read_only=False):
        """Mint a short-lived token restricted to one configured repository."""
        import jwt

        app_id = getattr(settings, "METADATA_GITHUB_APP_ID", "")
        key = getattr(settings, "METADATA_GITHUB_APP_PRIVATE_KEY", "")
        if not app_id or not key:
            raise ProposalError(
                "The Contributions App private key is not configured yet."
            )
        try:
            now = int(time.time())
            signed = jwt.encode(
                {"iat": now - 60, "exp": now + 540, "iss": str(app_id)},
                key,
                algorithm="RS256",
            )
        except (ValueError, TypeError, jwt.PyJWTError):
            raise ProposalError(
                "The Contributions App private key could not be used."
            ) from None
        app = cls(signed)
        try:
            installation = app.request(
                "GET", f"/repos/{config['repository']}/installation"
            )
            installation_id = installation["id"]
            if type(installation_id) is not int or installation_id <= 0:
                raise ProposalError("GitHub returned an invalid App installation.")
            result = app.request(
                "POST",
                f"/app/installations/{installation_id}/access_tokens",
                json={
                    "repositories": [config["repository"].split("/")[1]],
                    "permissions": {
                        "contents": "read" if read_only else "write",
                        "pull_requests": "read" if read_only else "write",
                    },
                },
            )
            if not isinstance(result.get("token"), str) or not result["token"]:
                raise ProposalError("GitHub did not issue an installation token.")
            return cls(result["token"], read_only=read_only)
        finally:
            app.session.close()

    @classmethod
    def reader(cls, config):
        # Tokens remain in process memory, separate from shared data caches.
        identity = (
            config["repository"],
            getattr(settings, "METADATA_GITHUB_APP_ID", ""),
            hashlib.sha256(
                getattr(settings, "METADATA_GITHUB_APP_PRIVATE_KEY", "").encode()
            ).hexdigest(),
        )
        with cls._token_lock:
            token, expires = cls._read_tokens.get(identity, ("", 0))
            if expires <= time.monotonic():
                api = cls.installation(config, read_only=True)
                try:
                    token = api.session.headers["Authorization"].removeprefix("Bearer ")
                finally:
                    api.session.close()
                if len(cls._read_tokens) >= 32:
                    cls._read_tokens.clear()
                cls._read_tokens[identity] = (token, time.monotonic() + 3000)
        return cls(token, read_only=True)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.session.close()

    def cached_request(self, path):
        key = "metadata-github-read:" + hashlib.sha256(path.encode()).hexdigest()
        value = cache.get(key)
        if value is None:
            value = self.request("GET", path)
            cache.set(key, value, 30)
        return value

    def request(self, method, path, **kwargs):
        if self.read_only and method != "GET":
            raise ProposalError("Metadata reads cannot write to GitHub.")
        if not path.startswith("/") or path.startswith("//"):
            raise ProposalError("Invalid GitHub API path.")
        try:
            response = self.session.request(
                method, "https://api.github.com" + path, timeout=(5, 20), **kwargs
            )
        except requests.RequestException as exc:
            raise ProposalError(
                "GitHub is unavailable. Your changes have not been published."
            ) from exc
        if response.status_code not in (200, 201, 202, 204):
            raise ProposalError(
                f"GitHub rejected {method} {path} (HTTP {response.status_code}). Check the Contributions App installation and repository permissions.",
                response.status_code,
            )
        return response.json() if response.content else None

    def pages(self, path):
        result = []
        for page in range(1, 31):
            values = self.request("GET", path, params={"per_page": 100, "page": page})
            result.extend(values)
            if len(values) < 100:
                return result
        raise ProposalError("This PR is too large for the metadata workflow.")

    def file(self, repository, path, ref):
        cache_key = None
        if self.read_only and re.fullmatch(r"[a-f0-9]{40}", ref):
            cache_key = (
                "metadata-github-file:"
                + hashlib.sha256(f"{repository}:{path}:{ref}".encode()).hexdigest()
            )
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
        value = self.request(
            "GET",
            f"/repos/{repository}/contents/{quote(path, safe='/')}",
            params={"ref": ref},
        )
        if (
            value.get("type") != "file"
            or value.get("encoding") != "base64"
            or value.get("size", 0) > 512000
        ):
            raise ProposalError("Expected a metadata file smaller than 512 KB.")
        try:
            result = (
                base64.b64decode(value["content"], validate=False).decode("utf-8"),
                value["sha"],
            )
            if cache_key:
                cache.set(cache_key, result, 3600)
            return result
        except (ValueError, UnicodeError) as exc:
            raise ProposalError("Metadata is not valid UTF-8.") from exc

    def approved_reviewer(self, repository, pr, require_override=False):
        from brainscore_metadata.review import review_exclusions

        if require_override and "metadata-source-override" not in {
            label["name"] for label in pr.get("labels", [])
        }:
            return ""
        reviews = self.pages(f"/repos/{repository}/pulls/{pr['number']}/reviews")
        excluded = review_exclusions(
            pr, self.pages(f"/repos/{repository}/pulls/{pr['number']}/commits")
        )
        latest = {}
        for review in reviews:
            if review["state"] in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
                latest[review["user"]["login"]] = review
        for user, review in latest.items():
            if (
                review["user"].get("type") != "User"
                or user.lower() in excluded
                or review["state"] != "APPROVED"
                or review.get("commit_id") != pr["head"]["sha"]
            ):
                continue
            access = self.request(
                "GET", f"/repos/{repository}/collaborators/{quote(user)}/permission"
            )
            if access.get("permission") in {"admin", "maintain", "write"}:
                return user
        return ""

    def override_reviewer(self, repository, pr):
        return self.approved_reviewer(repository, pr, require_override=True)

    def create_branch(self, config, nonce, user_id, github_login):
        branch = self.proposal_branch(nonce, user_id, github_login)
        repo = config["repository"]
        refs = self.request("GET", f"/repos/{repo}/git/matching-refs/heads/{branch}")
        if not any(ref.get("ref") == "refs/heads/" + branch for ref in refs):
            head = self.request(
                "GET", f"/repos/{repo}/git/ref/heads/{quote(config['branch'], safe='')}"
            )["object"]["sha"]
            self.request(
                "POST",
                f"/repos/{repo}/git/refs",
                json={"ref": "refs/heads/" + branch, "sha": head},
            )
        return branch

    @staticmethod
    def proposal_branch(nonce, user_id, github_login):
        if (
            type(user_id) is not int
            or user_id <= 0
            or not re.fullmatch(r"[A-Za-z0-9-]{1,39}", github_login)
        ):
            raise ProposalError(
                "A signed-in Brain-Score account and verified GitHub account are required."
            )
        return f"web_metadata_{user_id}_{github_login}_{hashlib.sha256(nonce.encode()).hexdigest()[:20]}/update_metadata"

    def create_proposal(
        self,
        config,
        path,
        base_blob,
        content,
        identifier,
        reason,
        nonce,
        *,
        user_id,
        github_login,
        preview_url=None,
    ):
        from brainscore_metadata import load, protected_changes

        repository = config["repository"]
        if not allowed_path(config, path):
            raise ProposalError("This file is not an allowed metadata file.")
        current, blob = self.file(repository, path, config["branch"])
        if blob != base_blob:
            raise ProposalError(
                "The metadata changed while you were editing. Reload and review your changes against the new version."
            )
        before, after = load(current), load(content)
        if (
            set(before["models"]) != set(after["models"])
            or before["domain"] != after["domain"]
        ):
            raise ProposalError("Model identities cannot be changed in this editor.")
        for key in before["models"]:
            if key != identifier and before["models"][key] != after["models"][key]:
                raise ProposalError("A proposal may only change the selected model.")
        if protected_changes(before["models"][identifier], after["models"][identifier]):
            raise ProposalError("The proposal changes a protected field.")
        branch = self.proposal_branch(nonce, user_id, github_login)

        def finish(pr):
            if preview_url and pr.get("number"):
                link = preview_url.format(number=pr["number"])
                body = pr.get("body") or ""
                if link not in body:
                    self.request(
                        "PATCH",
                        f"/repos/{repository}/pulls/{pr['number']}",
                        json={
                            "body": body
                            + "\n\n[Preview proposed metadata]("
                            + link
                            + ")"
                        },
                    )
            return pr["html_url"]

        existing = self.request(
            "GET",
            f"/repos/{repository}/pulls",
            params={
                "state": "all",
                "head": f"{repository.split('/')[0]}:{branch}",
                "base": config["branch"],
            },
        )
        if existing:
            return finish(existing[0])
        self.create_branch(config, nonce, user_id, github_login)
        branch_content, branch_blob = self.file(repository, path, branch)
        if branch_content != content:
            if branch_blob != base_blob:
                raise ProposalError(
                    "The proposal branch changed. Create a fresh proposal to avoid overwriting it."
                )
            self.request(
                "PUT",
                f"/repos/{repository}/contents/{quote(path, safe='/')}",
                json={
                    "message": "docs(metadata): update model metadata",
                    "branch": branch,
                    "sha": branch_blob,
                    "content": base64.b64encode(content.encode()).decode(),
                },
            )
        pr = self.request(
            "POST",
            f"/repos/{repository}/pulls",
            json={
                "title": f"Update metadata for {identifier[:180]} (user:{user_id})",
                "head": branch,
                "base": config["branch"],
                "body": f"Model: `{identifier}`\n\nBrain-Score user_id: {user_id}\nGitHub contributor: @{github_login}\n\n{reason}\n\nPlease review the field changes and supporting sources. Live metadata updates only after merge.",
            },
        )
        return finish(pr)
