import os
import re
import logging

import apprise

from restic_compose_backup.alerts.base import BaseAlert

logger = logging.getLogger(__name__)


def _parse_urls(value):
    """Split a comma/newline separated string into a clean list of URLs."""
    if not value:
        return []
    parts = re.split(r"[,\n]", value)
    return [part.strip() for part in parts if part.strip()]


class AppriseAlert(BaseAlert):
    name = "apprise"

    def __init__(self, urls):
        self.urls = urls

    @classmethod
    def create_from_env(cls):
        urls = _parse_urls(os.environ.get("APPRISE_URLS"))
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
        apobj.notify(title=subject or "", body=body or "")
