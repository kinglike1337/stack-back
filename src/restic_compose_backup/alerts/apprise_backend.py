import os
import re
import logging
from urllib.parse import urlencode

import apprise
from apprise import NotifyType
from apprise.common import OverflowMode

from restic_compose_backup.alerts.base import BaseAlert

logger = logging.getLogger(__name__)

# Prepended to a message body that was cut to fit the target's size limit.
TRUNCATION_NOTICE = "[... truncated, showing the end of the message ...]\n"

# Headroom below a target's limit for the few characters some plugins add
# (separators, formatting) on top of title and body.
SIZE_MARGIN = 64

# Discord webhook URLs as copied from the stable, PTB or Canary client, with or
# without an API version. Apprise only recognises the plain discord.com form.
_DISCORD_WEBHOOK_PREFIX = re.compile(
    r"^https://(?:(?:ptb|canary)\.)?discord(?:app)?\.com/api(?:/v\d+)?/webhooks/"
)


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
    # Reproduce the old smtp.py TLS behaviour: 465 -> implicit SSL, 587 ->
    # STARTTLS (mailtos default), any other port -> plain SMTP without TLS.
    scheme = "mailtos"
    if port == "465":
        params["mode"] = "ssl"
    elif port != "587":
        scheme = "mailto"
    return f"{scheme}://{host}:{port}?{urlencode(params)}"


def _legacy_discord_url():
    url = os.environ.get("DISCORD_WEBHOOK")
    if url and url.startswith("https://"):
        # The old backend posted to any https URL; map the client variants
        # onto the form Apprise parses natively.
        return _DISCORD_WEBHOOK_PREFIX.sub("https://discord.com/api/webhooks/", url)
    return None


def _legacy_urls() -> list[tuple[str, str]]:
    """Return (source, url) pairs for the deprecated EMAIL_* / DISCORD_WEBHOOK vars."""
    entries = []
    email_url = _legacy_email_url()
    if email_url:
        entries.append(("EMAIL_*", email_url))
    discord_url = _legacy_discord_url()
    if discord_url:
        entries.append(("DISCORD_WEBHOOK", discord_url))
    if entries:
        logger.warning(
            "%s deprecated and mapped onto Apprise internally. Configure APPRISE_URLS instead.",
            " and ".join(source for source, _ in entries),
        )
    return entries


def _fit_body(body: str, title: str, server) -> str:
    """Trim body so title and body fit the target's size limit, keeping the end.

    By default Apprise passes over-long messages through unchanged and
    services such as Discord (2000 characters) reject them. An alert body is
    often the whole backup log, whose end holds the error, so the tail is
    kept. Targets with an explicit ``?overflow=split`` or ``?overflow=truncate``
    are left to Apprise.
    """
    if server.overflow_mode != OverflowMode.UPSTREAM:
        return body
    limit = server.body_maxlen - SIZE_MARGIN
    if server.title_maxlen <= 0 or getattr(server, "overflow_amalgamate_title", False):
        # The title shares the body's budget on these targets
        limit -= len(title)
    if len(body) <= limit:
        return body
    keep = max(limit - len(TRUNCATION_NOTICE), 0)
    return TRUNCATION_NOTICE + body[-keep:] if keep else ""


class AppriseAlert(BaseAlert):
    name = "apprise"

    def __init__(self, urls: list[str], sources: list[str] | None = None):
        self.urls = urls
        # Human-readable origin of each URL, used in log messages
        self.sources = sources or [f"URL #{i}" for i in range(1, len(urls) + 1)]

    @classmethod
    def create_from_env(cls):
        urls = _parse_urls(os.environ.get("APPRISE_URLS"))
        sources = [f"APPRISE_URLS entry #{i}" for i in range(1, len(urls) + 1)]
        for source, url in _legacy_urls():
            urls.append(url)
            sources.append(source)
        instance = cls(urls, sources)
        if instance.properly_configured:
            return instance
        return None

    @property
    def properly_configured(self) -> bool:
        return len(self.urls) > 0

    def send(self, subject=None, body=None, alert_type=None):
        apobj = apprise.Apprise()
        for url, source in zip(self.urls, self.sources):
            if not apobj.add(url):
                logger.warning(
                    "Apprise could not load (all URLs of) %s; check it for typos",
                    source,
                )
        if len(apobj) == 0:
            logger.error("No valid Apprise notification target; alert not sent")
            return

        notify_type = (
            NotifyType.FAILURE
            if str(alert_type).upper() == "ERROR"
            else NotifyType.INFO
        )
        title = subject or ""
        body = body or ""

        # Notify each target separately so every one gets a body that fits its
        # own size limit (e.g. Discord 2000, Pushover 1024, email 32768).
        failed = 0
        for server in apobj:
            target = apprise.Apprise()
            target.add(server)
            if not target.notify(
                title=title,
                body=_fit_body(body, title, server),
                notify_type=notify_type,
            ):
                failed += 1
        if failed:
            logger.error(
                "Apprise failed to deliver notification to %d of %d targets",
                failed,
                len(apobj),
            )
