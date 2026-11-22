"""Unit tests for cli.cleanup() and cli.maintenance() exit-code handling"""

from types import SimpleNamespace
from unittest import mock

import pytest

from restic_compose_backup import cli
from .conftest import BaseTestCase

pytestmark = pytest.mark.unit


def _make_config():
    return SimpleNamespace(
        repository="rest:http://example.invalid/repo",
        keep_daily="7",
        keep_weekly="4",
        keep_monthly="12",
        keep_yearly="3",
        check_with_cache="false",
    )


class CleanupExitCodeTests(BaseTestCase):
    """cleanup() must return the first non-zero exit code of forget and prune"""

    def test_both_succeed_returns_zero(self):
        with (
            mock.patch.object(cli.restic, "forget", return_value=0) as forget,
            mock.patch.object(cli.restic, "prune", return_value=0) as prune,
        ):
            result = cli.cleanup(_make_config(), containers=None)

        self.assertEqual(result, 0)
        forget.assert_called_once()
        prune.assert_called_once()

    def test_failed_forget_with_successful_prune_returns_forget_code(self):
        with (
            mock.patch.object(cli.restic, "forget", return_value=3),
            mock.patch.object(cli.restic, "prune", return_value=0),
        ):
            result = cli.cleanup(_make_config(), containers=None)

        self.assertEqual(result, 3)

    def test_successful_forget_with_failed_prune_returns_prune_code(self):
        with (
            mock.patch.object(cli.restic, "forget", return_value=0),
            mock.patch.object(cli.restic, "prune", return_value=1),
        ):
            result = cli.cleanup(_make_config(), containers=None)

        self.assertEqual(result, 1)

    def test_both_fail_returns_first_nonzero_code(self):
        with (
            mock.patch.object(cli.restic, "forget", return_value=3),
            mock.patch.object(cli.restic, "prune", return_value=1),
        ):
            result = cli.cleanup(_make_config(), containers=None)

        self.assertEqual(result, 3)

    def test_maintenance_exits_and_skips_check_when_forget_fails_and_prune_succeeds(
        self,
    ):
        with (
            mock.patch.object(cli.restic, "forget", return_value=3),
            mock.patch.object(cli.restic, "prune", return_value=0),
            mock.patch.object(cli.restic, "check", return_value=0) as check,
        ):
            with self.assertRaises(SystemExit) as ctx:
                cli.maintenance(_make_config(), containers=None)

        self.assertEqual(ctx.exception.code, 1)
        check.assert_not_called()

    def test_maintenance_exits_and_skips_check_when_forget_succeeds_and_prune_fails(
        self,
    ):
        with (
            mock.patch.object(cli.restic, "forget", return_value=0),
            mock.patch.object(cli.restic, "prune", return_value=1),
            mock.patch.object(cli.restic, "check", return_value=0) as check,
        ):
            with self.assertRaises(SystemExit) as ctx:
                cli.maintenance(_make_config(), containers=None)

        self.assertEqual(ctx.exception.code, 1)
        check.assert_not_called()
