"""Unit tests for Config env-var reading and validation"""

import os
from unittest import mock

import pytest

from restic_compose_backup.config import Config
from .conftest import BaseTestCase

pytestmark = pytest.mark.unit

PASSWORD_VARS = ("RESTIC_PASSWORD", "RESTIC_PASSWORD_FILE", "RESTIC_PASSWORD_COMMAND")


def password_env(**values):
    """Patch os.environ so only the given password variables are set"""
    env = {k: v for k, v in os.environ.items() if k not in PASSWORD_VARS}
    env.update(values)
    return mock.patch.dict(os.environ, env, clear=True)


class ConfigPasswordTests(BaseTestCase):
    """Tests that Config reads RESTIC_PASSWORD (not RESTIC_REPOSITORY)"""

    def test_password_reads_restic_password_env(self):
        """Config.password must read the RESTIC_PASSWORD env var"""
        with password_env(RESTIC_PASSWORD="supersecret"):
            config = Config(check=False)
        self.assertEqual(config.password, "supersecret")

    def test_password_is_not_repository(self):
        """Config.password must not mirror the repository URL (regression guard)"""
        with password_env(RESTIC_PASSWORD="supersecret"):
            config = Config(check=False)
        self.assertNotEqual(config.password, config.repository)

    def test_check_raises_when_password_missing(self):
        """check() must raise when no password source is set"""
        with password_env():
            with self.assertRaises(ValueError):
                Config(check=True)

    def test_check_accepts_password_file(self):
        """RESTIC_PASSWORD_FILE alone is a valid password source"""
        with password_env(RESTIC_PASSWORD_FILE="/run/secrets/restic_password"):
            config = Config(check=True)
        self.assertEqual(config.password_file, "/run/secrets/restic_password")

    def test_check_accepts_password_command(self):
        """RESTIC_PASSWORD_COMMAND alone is a valid password source"""
        with password_env(RESTIC_PASSWORD_COMMAND="cat /run/secrets/restic_password"):
            config = Config(check=True)
        self.assertEqual(config.password_command, "cat /run/secrets/restic_password")
