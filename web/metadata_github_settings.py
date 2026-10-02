"""Load contributor App settings without exposing credentials in diagnostics."""

import json
import re
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

SECRET_FIELDS = {
    "METADATA_GITHUB_APP_ID": "GITHUB_APP_ID",
    "METADATA_GITHUB_APP_PRIVATE_KEY": "GITHUB_APP_PRIVATE_KEY",
    "METADATA_GITHUB_CLIENT_ID": "GITHUB_CLIENT_ID",
    "METADATA_GITHUB_CLIENT_SECRET": "GITHUB_CLIENT_SECRET",
    "METADATA_GITHUB_APP_SLUG": "GITHUB_APP_SLUG",
    "METADATA_GITHUB_CALLBACK_URL": "GITHUB_CALLBACK_URL",
}

PRODUCTION_HOSTS = {"brain-score.org", "www.brain-score.org"}
PRODUCTION_CALLBACK = "https://www.brain-score.org/metadata/github/callback/"
CONTRIBUTIONS_SECRET = "Brain-Score_Contributions_GitHub_App"


def production_site(environ):
    """Recognize deployment configuration, never an incoming request hostname."""
    if environ.get("DJANGO_ENV") in {"development", "staging", "test"}:
        return False
    hosts = {host.strip().lower() for host in environ.get("DOMAIN", "").split(":")}
    return bool(hosts & PRODUCTION_HOSTS)


def read_secret(name, region):
    import boto3
    from botocore.config import Config

    client = boto3.client(
        "secretsmanager",
        region_name=region,
        config=Config(connect_timeout=5, read_timeout=10, retries={"max_attempts": 1}),
    )
    return json.loads(client.get_secret_value(SecretId=name)["SecretString"])


def load_metadata_github_settings(environ, secret_reader=None):
    production = production_site(environ)
    enabled = environ.get("MODEL_METADATA_EDIT_ENABLED", "1" if production else "0") == "1"
    name = environ.get(
        "METADATA_GITHUB_SECRET_NAME", CONTRIBUTIONS_SECRET if production and enabled else ""
    )
    region = environ.get("METADATA_GITHUB_SECRET_REGION", "us-east-2")
    values = {}
    if name:
        try:
            values = (secret_reader or read_secret)(name, region)
            if not isinstance(values, dict):
                raise ValueError()
        except Exception:
            raise ImproperlyConfigured(
                "Unable to load the metadata GitHub App secret."
            ) from None

    config = {}
    for setting, field in SECRET_FIELDS.items():
        default = (
            PRODUCTION_CALLBACK
            if setting == "METADATA_GITHUB_CALLBACK_URL" and production and enabled
            else values.get(field, "")
        )
        value = environ.get(setting, default)
        if not isinstance(value, str):
            raise ImproperlyConfigured(f"{setting} must be text.")
        config[setting] = value.strip()

    # Some secret entries use the display name. The App's public link contains
    # the canonical slug, so registration details do not need to be rewritten.
    slug = config["METADATA_GITHUB_APP_SLUG"]
    if not slug or not re.fullmatch(r"[A-Za-z0-9-]+", slug):
        match = re.fullmatch(
            r"https://github\.com/apps/([a-zA-Z0-9-]+)/?",
            str(values.get("GITHUB_PUBLIC_LINK", "")),
        )
        if match:
            config["METADATA_GITHUB_APP_SLUG"] = match.group(1).lower()
        elif name or enabled:
            raise ImproperlyConfigured(
                "Metadata GitHub App needs a valid App slug or public link."
            )

    if name or enabled:
        for setting, value in config.items():
            if not enabled and setting in {
                "METADATA_GITHUB_APP_ID",
                "METADATA_GITHUB_APP_PRIVATE_KEY",
            }:
                continue
            if not value:
                raise ImproperlyConfigured(
                    f"{setting} is required for the metadata GitHub App."
                )
    callback = config["METADATA_GITHUB_CALLBACK_URL"]
    if callback:
        try:
            url = urlsplit(callback)
            local_http = url.scheme == "http" and url.hostname in {
                "127.0.0.1",
                "localhost",
                "::1",
            }
            valid = (
                (url.scheme == "https" or local_http)
                and bool(url.hostname)
                and not url.username
                and not url.password
                and url.path == "/metadata/github/callback/"
                and not url.query
                and not url.fragment
            )
            url.port
        except ValueError:
            valid = False
        if not valid:
            raise ImproperlyConfigured(
                "Metadata GitHub callback must be an HTTPS callback URL, or HTTP on loopback for local testing."
            )
    config.update(
        MODEL_METADATA_EDIT_ENABLED=enabled,
        METADATA_GITHUB_SECRET_NAME=name,
        METADATA_GITHUB_SECRET_REGION=region,
    )
    return config
