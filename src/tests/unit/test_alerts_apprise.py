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
