"""Unit tests for the Apprise notification backend."""

import json
import os
import unittest
from contextlib import contextmanager
from unittest import mock

import apprise
import pytest

from restic_compose_backup.alerts.apprise_backend import (
    TRUNCATION_NOTICE,
    AppriseAlert,
    _fit_body,
)

LOGGER = "restic_compose_backup.alerts.apprise_backend"
DISCORD_URL = "https://discord.com/api/webhooks/1/abc"


@contextmanager
def fake_http(status_code=200):
    """Intercept the HTTP calls Apprise plugins make; yields the two mocks.

    The json:// plugin uses requests.request, Discord uses requests.post.
    """
    with (
        mock.patch("requests.request") as m_request,
        mock.patch("requests.post") as m_post,
    ):
        for m in (m_request, m_post):
            m.return_value.status_code = status_code
            m.return_value.content = b""
        yield m_request, m_post


def json_payloads(m_request):
    return [json.loads(call.kwargs["data"]) for call in m_request.call_args_list]


@pytest.mark.unit
class AppriseAlertTests(unittest.TestCase):
    def test_apprise_urls_single(self):
        env = {"APPRISE_URLS": "pover://user@token"}
        with mock.patch.dict(os.environ, env, clear=True):
            instance = AppriseAlert.create_from_env()
        self.assertIsNotNone(instance)
        self.assertEqual(instance.urls, ["pover://user@token"])

    def test_apprise_urls_split_on_newlines_only(self):
        # Entries are split on newlines only; commas are left intact so that
        # Apprise can split URL lists itself without breaking a comma that
        # belongs inside a single URL (e.g. a multi-recipient mailto).
        env = {
            "APPRISE_URLS": "json://localhost,pover://user@token\n"
            "mailtos://u:p@mail.example.com?to=a@example.com,b@example.com\n"
            "  "  # blank/whitespace line is dropped
        }
        with mock.patch.dict(os.environ, env, clear=True):
            instance = AppriseAlert.create_from_env()
        self.assertEqual(
            instance.urls,
            [
                "json://localhost,pover://user@token",
                "mailtos://u:p@mail.example.com?to=a@example.com,b@example.com",
            ],
        )

    def test_apprise_expands_comma_lists_but_keeps_in_url_commas(self):
        # End-to-end: a comma-separated line expands into multiple Apprise
        # targets, while a comma inside one URL (multi-recipient mailto) stays
        # part of that single target.
        import apprise

        listed = apprise.Apprise()
        self.assertTrue(listed.add("json://localhost,pover://user@token"))
        self.assertEqual(len(listed), 2)

        mail = apprise.Apprise()
        self.assertTrue(
            mail.add("mailtos://u:p@mail.example.com?to=a@example.com,b@example.com")
        )
        self.assertEqual(len(mail), 1)
        recipients = [addr for _, addr in mail[0].targets]
        self.assertEqual(recipients, ["a@example.com", "b@example.com"])

    def test_no_config_returns_none(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            instance = AppriseAlert.create_from_env()
        self.assertIsNone(instance)

    def test_legacy_email_port_465_uses_ssl(self):
        env = {
            "EMAIL_HOST": "mail.example.com",
            "EMAIL_PORT": "465",
            "EMAIL_HOST_USER": "u@example.com",
            "EMAIL_HOST_PASSWORD": "secret",
            "EMAIL_SEND_TO": "a@example.com,b@example.com",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            instance = AppriseAlert.create_from_env()
        self.assertEqual(len(instance.urls), 1)
        url = instance.urls[0]
        self.assertTrue(url.startswith("mailtos://mail.example.com:465?"))
        self.assertIn("mode=ssl", url)

        import apprise

        apobj = apprise.Apprise()
        self.assertTrue(apobj.add(url))
        recipients = [addr for _, addr in apobj[0].targets]
        self.assertEqual(recipients, ["a@example.com", "b@example.com"])

    def test_legacy_email_port_587_no_ssl(self):
        env = {
            "EMAIL_HOST": "mail.example.com",
            "EMAIL_PORT": "587",
            "EMAIL_HOST_USER": "u@example.com",
            "EMAIL_SEND_TO": "a@example.com",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            instance = AppriseAlert.create_from_env()
        self.assertNotIn("mode=ssl", instance.urls[0])

    def test_legacy_email_other_port_uses_insecure_mailto(self):
        # The old SMTP backend sent plain (no TLS) for any port other than
        # 465/587. Reproduce that for backward compatibility: ports != 465/587
        # map to the insecure ``mailto://`` scheme, not ``mailtos://``.
        env = {
            "EMAIL_HOST": "relay.internal",
            "EMAIL_PORT": "25",
            "EMAIL_HOST_USER": "u@example.com",
            "EMAIL_SEND_TO": "a@example.com",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            instance = AppriseAlert.create_from_env()
        url = instance.urls[0]
        self.assertTrue(url.startswith("mailto://relay.internal:25?"))
        self.assertNotIn("mode=ssl", url)

    def test_legacy_email_incomplete_ignored(self):
        env = {
            "EMAIL_HOST": "mail.example.com",
            "EMAIL_PORT": "587",
            "EMAIL_HOST_USER": "u@example.com",
            # EMAIL_SEND_TO missing -> no mail target
        }
        with mock.patch.dict(os.environ, env, clear=True):
            instance = AppriseAlert.create_from_env()
        self.assertIsNone(instance)

    def test_legacy_discord_passed_through(self):
        webhook = "https://discord.com/api/webhooks/1/abc"
        env = {"DISCORD_WEBHOOK": webhook}
        with mock.patch.dict(os.environ, env, clear=True):
            instance = AppriseAlert.create_from_env()
        self.assertIn(webhook, instance.urls)

    def test_apprise_and_legacy_combined_with_warning(self):
        env = {
            "APPRISE_URLS": "pover://user@token",
            "DISCORD_WEBHOOK": "https://discord.com/api/webhooks/1/abc",
        }
        logger_name = "restic_compose_backup.alerts.apprise_backend"
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertLogs(logger_name, level="WARNING") as cm:
                instance = AppriseAlert.create_from_env()
        self.assertEqual(len(instance.urls), 2)
        self.assertTrue(any("deprecated" in line for line in cm.output))

    def test_legacy_discord_client_variants_normalised(self):
        # Webhook URLs copied from the PTB/Canary client or with an API version
        # worked with the old backend; Apprise only parses the plain form.
        for webhook in [
            "https://ptb.discord.com/api/webhooks/1/abc",
            "https://canary.discord.com/api/v10/webhooks/1/abc",
            "https://discordapp.com/api/webhooks/1/abc",
        ]:
            with self.subTest(webhook=webhook):
                with mock.patch.dict(
                    os.environ, {"DISCORD_WEBHOOK": webhook}, clear=True
                ):
                    instance = AppriseAlert.create_from_env()
                self.assertEqual(instance.urls, [DISCORD_URL])
                self.assertTrue(apprise.Apprise().add(instance.urls[0]))

    def test_sources_name_each_url(self):
        env = {
            "APPRISE_URLS": "json://localhost\npover://user@token",
            "DISCORD_WEBHOOK": DISCORD_URL,
        }
        with mock.patch.dict(os.environ, env, clear=True):
            instance = AppriseAlert.create_from_env()
        self.assertEqual(
            instance.sources,
            ["APPRISE_URLS entry #1", "APPRISE_URLS entry #2", "DISCORD_WEBHOOK"],
        )

    def test_send_notifies_each_target(self):
        alert = AppriseAlert(["json://localhost", "json://otherhost"])
        with fake_http() as (m_request, _):
            alert.send(subject="[INFO] Backup done", body="boom", alert_type="INFO")
        hosts = [call.args[1] for call in m_request.call_args_list]
        self.assertEqual(sorted(hosts), ["http://localhost", "http://otherhost"])
        for payload in json_payloads(m_request):
            self.assertEqual(payload["title"], "[INFO] Backup done")
            self.assertEqual(payload["message"], "boom")
            self.assertEqual(payload["type"], "info")

    def test_send_maps_error_alert_type_to_failure(self):
        alert = AppriseAlert(["json://localhost"])
        with fake_http() as (m_request, _):
            alert.send(subject="[ERROR] Backup failed", body="boom", alert_type="ERROR")
        self.assertEqual(json_payloads(m_request)[0]["type"], "failure")

    def test_send_logs_error_on_notify_failure(self):
        alert = AppriseAlert(["json://localhost"])
        with fake_http(status_code=500):
            with self.assertLogs(LOGGER, level="ERROR") as cm:
                alert.send(subject="[ERROR] x", body="y")
        self.assertTrue(any("failed to deliver" in line for line in cm.output))

    def test_send_warns_on_rejected_url(self):
        # A typo'd URL is rejected by Apprise's add(). The backend must name
        # it instead of silently dropping the target, and still notify the rest.
        alert = AppriseAlert(["json://localhost", "bogus"])
        with fake_http() as (m_request, _):
            with self.assertLogs(LOGGER, level="WARNING") as cm:
                alert.send(subject="[INFO] x", body="y")
        self.assertTrue(any("URL #2" in line for line in cm.output))
        self.assertEqual(m_request.call_count, 1)

    def test_send_without_valid_target_logs_error(self):
        alert = AppriseAlert(["bogus"])
        with self.assertLogs(LOGGER, level="ERROR") as cm:
            alert.send(subject="[INFO] x", body="y")
        self.assertTrue(any("No valid" in line for line in cm.output))

    def test_discord_long_body_trimmed_keeping_the_end(self):
        # A failed backup sends the whole backup log. Discord rejects messages
        # over 2000 characters, so only the end (where the error is) is sent.
        log = "\n".join(f"line {i} " + "x" * 80 for i in range(200))
        log += "\nFatal: unable to save snapshot"
        alert = AppriseAlert([DISCORD_URL])
        with fake_http(status_code=204) as (_, m_post):
            alert.send(
                subject="[ERROR] Backup process exited with non-zero code",
                body=log,
                alert_type="ERROR",
            )
        content = json.loads(m_post.call_args.kwargs["data"])["content"]
        self.assertLessEqual(len(content), 2000)
        self.assertIn(TRUNCATION_NOTICE.strip(), content)
        self.assertTrue(content.endswith("Fatal: unable to save snapshot"))

    def test_short_body_is_not_trimmed(self):
        server = apprise.Apprise.instantiate(DISCORD_URL)
        self.assertEqual(_fit_body("short", "title", server), "short")

    def test_explicit_overflow_mode_left_to_apprise(self):
        # ?overflow=split asks Apprise to send the full text in several parts.
        server = apprise.Apprise.instantiate(DISCORD_URL + "?overflow=split")
        body = "x" * 5000
        self.assertEqual(_fit_body(body, "title", server), body)
