"""Unit tests for the Apprise notification backend."""

import os
import unittest
from unittest import mock

import pytest

from restic_compose_backup.alerts.apprise_backend import AppriseAlert


@pytest.mark.unit
class AppriseAlertTests(unittest.TestCase):
    def test_apprise_urls_single(self):
        env = {"APPRISE_URLS": "pover://user@token"}
        with mock.patch.dict(os.environ, env, clear=True):
            instance = AppriseAlert.create_from_env()
        self.assertIsNotNone(instance)
        self.assertEqual(instance.urls, ["pover://user@token"])

    def test_apprise_urls_comma_and_newline(self):
        env = {"APPRISE_URLS": "a://x, b://y\nc://z ,"}
        with mock.patch.dict(os.environ, env, clear=True):
            instance = AppriseAlert.create_from_env()
        self.assertEqual(instance.urls, ["a://x", "b://y", "c://z"])

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

    def test_legacy_email_incomplete_ignored(self):
        env = {
            "EMAIL_HOST": "mail.example.com",
            "EMAIL_PORT": "587",
            "EMAIL_HOST_USER": "u@example.com",
            # EMAIL_SEND_TO fehlt -> kein Mail-Ziel
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

    def test_send_adds_urls_and_notifies(self):
        alert = AppriseAlert(["pover://user@token", "discord://1/abc"])
        with mock.patch(
            "restic_compose_backup.alerts.apprise_backend.apprise"
        ) as m_apprise:
            alert.send(subject="[ERROR] Backup failed", body="boom")
        apobj = m_apprise.Apprise.return_value
        self.assertEqual(apobj.add.call_count, 2)
        apobj.notify.assert_called_once_with(title="[ERROR] Backup failed", body="boom")
