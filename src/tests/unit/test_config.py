"""Unit tests for Config env-var reading and validation"""

import pytest

from restic_compose_backup import utils
from restic_compose_backup.config import Config
from .conftest import BaseTestCase

pytestmark = pytest.mark.unit


class ConfigPasswordTests(BaseTestCase):
    """Tests that Config reads RESTIC_PASSWORD (not RESTIC_REPOSITORY)"""

    def test_password_reads_restic_password_env(self):
        """Config.password must read the RESTIC_PASSWORD env var"""
        with utils.environment("RESTIC_PASSWORD", "supersecret"):
            config = Config(check=False)
        self.assertEqual(config.password, "supersecret")

    def test_password_is_not_repository(self):
        """Config.password must not mirror the repository URL (regression guard)"""
        with utils.environment("RESTIC_PASSWORD", "supersecret"):
            config = Config(check=False)
        self.assertNotEqual(config.password, config.repository)

    def test_check_raises_when_password_missing(self):
        """check() must raise when RESTIC_PASSWORD is not set"""
        with utils.environment("RESTIC_PASSWORD", ""):
            with self.assertRaises(ValueError):
                Config(check=True)
