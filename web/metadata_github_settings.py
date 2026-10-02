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
    name = environ.get("METADATA_GITHUB_SECRET_NAME", "")
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
        value = environ.get(setting, values.get(field, ""))
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
        elif name or environ.get("MODEL_METADATA_EDIT_ENABLED") == "1":
            raise ImproperlyConfigured(
                "Metadata GitHub App needs a valid App slug or public link."
            )

    enabled = environ.get("MODEL_METADATA_EDIT_ENABLED") == "1"
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
    return config
