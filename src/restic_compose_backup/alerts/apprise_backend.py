import os
import logging
from urllib.parse import urlencode

import apprise

from restic_compose_backup.alerts.base import BaseAlert

logger = logging.getLogger(__name__)


def _parse_urls(value: str | None) -> list[str]:
    """Split a newline-separated string into a clean list of URL entries.

    Splitting is intentionally newline-only. Apprise's own ``add()`` already
    splits comma-separated URL lists while preserving commas that belong to a
    single URL (e.g. a multi-recipient ``mailto`` ``to=a@x,b@y``), so comma
    handling is left to it; pre-splitting on commas here would corrupt such
    URLs.
    """
    if not value:
        return []
    return [line.strip() for line in value.splitlines() if line.strip()]


def _legacy_email_url():
    host = os.environ.get("EMAIL_HOST")
    port = os.environ.get("EMAIL_PORT")
    user = os.environ.get("EMAIL_HOST_USER")
    password = os.environ.get("EMAIL_HOST_PASSWORD") or ""
    recipients = [
        addr.strip()
        for addr in (os.environ.get("EMAIL_SEND_TO") or "").split(",")
        if addr.strip()
    ]
    if not (host and port and user and recipients):
        return None
    params = {
        "user": user,
        "pass": password,
        "from": user,
        "to": ",".join(recipients),
    }
    if port == "465":
        params["mode"] = "ssl"
    return f"mailtos://{host}:{port}?{urlencode(params)}"


def _legacy_discord_url():
    url = os.environ.get("DISCORD_WEBHOOK")
    if isinstance(url, str) and url.startswith("https://"):
        return url
    return None


def _legacy_urls():
    urls = []
    sources = []
    email_url = _legacy_email_url()
    if email_url:
        urls.append(email_url)
        sources.append("EMAIL_*")
    discord_url = _legacy_discord_url()
    if discord_url:
        urls.append(discord_url)
        sources.append("DISCORD_WEBHOOK")
    if urls:
        logger.warning(
            "%s deprecated and mapped onto Apprise internally. Configure APPRISE_URLS instead.",
            " and ".join(sources),
        )
    return urls


class AppriseAlert(BaseAlert):
    name = "apprise"

    def __init__(self, urls: list[str]):
        self.urls = urls

    @classmethod
    def create_from_env(cls):
        urls = _parse_urls(os.environ.get("APPRISE_URLS"))
        urls += _legacy_urls()
        instance = cls(urls)
        if instance.properly_configured:
            return instance
        return None

    @property
    def properly_configured(self) -> bool:
        return len(self.urls) > 0

    def send(self, subject=None, body=None, alert_type=None):
        apobj = apprise.Apprise()
        for url in self.urls:
            apobj.add(url)
        if not apobj.notify(title=subject or "", body=body or ""):
            logger.error(
                "Apprise failed to deliver notification to one or more targets"
            )
