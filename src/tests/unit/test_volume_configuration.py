"""Unit tests for volume backup configuration"""

from unittest import mock
import pytest

from restic_compose_backup.containers import RunningContainers
from . import fixtures
from .conftest import BaseTestCase

pytestmark = pytest.mark.unit

list_containers_func = "restic_compose_backup.utils.list_containers"


class VolumeConfigurationTests(BaseTestCase):
    """Tests for volume backup configuration and filtering"""

    def test_volumes_for_backup(self):
        """Test identifying volumes marked for backup"""
        containers = self.createContainers()
        containers += [
            {
                "service": "web",
                "labels": {
                    "stack-back.volumes": True,
                },
                "mounts": [
                    {
                        "Source": "test",
                        "Destination": "test",
                        "Type": "bind",
                    }
                ],
            },
            {
                "service": "mysql",
                "labels": {
                    "stack-back.mysql": True,
                },
                "mounts": [
                    {
                        "Source": "data",
                        "Destination": "data",
                        "Type": "bind",
                    }
                ],
            },
        ]
        with mock.patch(
            list_containers_func, fixtures.containers(containers=containers)
        ):
            cnt = RunningContainers()
            self.assertTrue(len(cnt.containers_for_backup()) == 2)
            self.assertEqual(
                cnt.generate_backup_mounts(),
                {"test": {"bind": "/volumes/web/test", "mode": "ro"}},
            )
        mysql_service = cnt.get_service("mysql")
        self.assertNotEqual(mysql_service, None, msg="MySQL service not found")
        mounts = mysql_service.filter_mounts()
        print(mounts)
        self.assertTrue(mysql_service.mysql_backup_enabled)
        self.assertEqual(len(mounts), 0)

    def test_no_volumes_for_backup(self):
        """Test containers with no volumes to backup"""
        containers = self.createContainers()
        containers += [
            {
                "service": "web",
                "labels": {
                    "stack-back.volumes": True,
                },
            },
        ]
        with mock.patch(
            list_containers_func, fixtures.containers(containers=containers)
        ):
            cnt = RunningContainers()
            self.assertTrue(len(cnt.containers_for_backup()) == 1)
        web_service = cnt.get_service("web")
        self.assertNotEqual(web_service, None, msg="Web service not found")
        mounts = web_service.filter_mounts()
        print(mounts)
        self.assertEqual(len(mounts), 0)

    def test_include(self):
        """Test including specific volumes by name"""
        containers = self.createContainers()
        containers += [
            {
                "service": "web",
                "labels": {
                    "stack-back.volumes": True,
                    "stack-back.volumes.include": "media",
                },
                "mounts": [
                    {
                        "Source": "/srv/files/media",
                        "Destination": "/srv/media",
                        "Type": "bind",
                    },
                    {
                        "Source": "/srv/files/stuff",
                        "Destination": "/srv/stuff",
                        "Type": "bind",
                    },
                ],
            },
        ]
        with mock.patch(
            list_containers_func, fixtures.containers(containers=containers)
        ):
            cnt = RunningContainers()

        web_service = cnt.get_service("web")
        self.assertNotEqual(web_service, None, msg="Web service not found")

        mounts = web_service.filter_mounts()
        print(mounts)
        self.assertEqual(len(mounts), 1)
        self.assertEqual(mounts[0].source, "/srv/files/media")

    def test_exclude(self):
        """Test excluding specific volumes by name"""
        containers = self.createContainers()
        containers += [
            {
                "service": "web",
                "labels": {
                    "stack-back.volumes": True,
                    "stack-back.volumes.exclude": "stuff",
                },
                "mounts": [
                    {
                        "Source": "/srv/files/media",
                        "Destination": "/srv/media",
                        "Type": "bind",
                    },
                    {
                        "Source": "/srv/files/stuff",
                        "Destination": "/srv/stuff",
                        "Type": "bind",
                    },
                ],
            },
        ]
        with mock.patch(
            list_containers_func, fixtures.containers(containers=containers)
        ):
            cnt = RunningContainers()

        web_service = cnt.get_service("web")
        self.assertNotEqual(web_service, None, msg="Web service not found")

        mounts = web_service.filter_mounts()
        self.assertEqual(len(mounts), 1)
        self.assertEqual(mounts[0].source, "/srv/files/media")

    def test_stop_container_during_backup_volume(self):
        """Test stopping containers during volume backup"""
        containers = self.createContainers()
        containers += [
            {
                "service": "web",
                "labels": {
                    "stack-back.volumes": True,
                    "stack-back.volumes.include": "sqlite",
                    "stack-back.volumes.stop-during-backup": True,
                },
                "mounts": [
                    {
                        "Source": "/srv/files/media",
                        "Destination": "/srv/media",
                        "Type": "bind",
                    },
                    {
                        "Source": "/srv/files/sqlite",
                        "Destination": "/srv/sqlite",
                        "Type": "bind",
                    },
                ],
            }
        ]
        with mock.patch(
            list_containers_func, fixtures.containers(containers=containers)
        ):
            cnt = RunningContainers()
        web_service = cnt.get_service("web")
        self.assertNotEqual(web_service, None, msg="Web service not found")
        self.assertTrue(web_service.stop_during_backup)

    def test_bind_excluded_by_default_under_exclude_bind_mounts(self):
        """Bind mounts are stripped when EXCLUDE_BIND_MOUNTS=true and no include is set."""
        containers = self.createContainers()
        containers += [
            {
                "service": "web",
                "labels": {
                    "stack-back.volumes": True,
                },
                "mounts": [
                    {
                        "Source": "/srv/files/data",
                        "Destination": "/srv/data",
                        "Type": "bind",
                    }
                ],
            },
        ]
        with mock.patch(
            list_containers_func, fixtures.containers(containers=containers)
        ):
            cnt = RunningContainers()
        web_service = cnt.get_service("web")
        with mock.patch(
            "restic_compose_backup.config.config.exclude_bind_mounts", True
        ):
            self.assertEqual(len(web_service.filter_mounts()), 0)

    def test_bind_resurrected_by_include(self):
        """A bind mount matching stack-back.volumes.include is kept despite EXCLUDE_BIND_MOUNTS."""
        containers = self.createContainers()
        containers += [
            {
                "service": "web",
                "labels": {
                    "stack-back.volumes": True,
                    "stack-back.volumes.include": "data",
                },
                "mounts": [
                    {
                        "Source": "/srv/files/data",
                        "Destination": "/srv/data",
                        "Type": "bind",
                    }
                ],
            },
        ]
        with mock.patch(
            list_containers_func, fixtures.containers(containers=containers)
        ):
            cnt = RunningContainers()
        web_service = cnt.get_service("web")
        with mock.patch(
            "restic_compose_backup.config.config.exclude_bind_mounts", True
        ):
            mounts = web_service.filter_mounts()
        self.assertEqual(len(mounts), 1)
        self.assertEqual(mounts[0].source, "/srv/files/data")

    def test_include_pattern_not_matching_keeps_bind_excluded(self):
        """A non-matching include pattern does not resurrect a bind."""
        containers = self.createContainers()
        containers += [
            {
                "service": "web",
                "labels": {
                    "stack-back.volumes": True,
                    "stack-back.volumes.include": "nomatch",
                },
                "mounts": [
                    {
                        "Source": "/srv/files/data",
                        "Destination": "/srv/data",
                        "Type": "bind",
                    }
                ],
            },
        ]
        with mock.patch(
            list_containers_func, fixtures.containers(containers=containers)
        ):
            cnt = RunningContainers()
        web_service = cnt.get_service("web")
        with mock.patch(
            "restic_compose_backup.config.config.exclude_bind_mounts", True
        ):
            self.assertEqual(len(web_service.filter_mounts()), 0)

    def test_volume_unaffected_by_resurrection(self):
        """Named volumes are still backed up under EXCLUDE_BIND_MOUNTS."""
        containers = self.createContainers()
        containers += [
            {
                "service": "web",
                "labels": {
                    "stack-back.volumes": True,
                    "stack-back.volumes.include": "data",
                },
                "mounts": [
                    {
                        "Source": "web_data",
                        "Destination": "/usr/share/nginx/html",
                        "Type": "volume",
                    }
                ],
            },
        ]
        with mock.patch(
            list_containers_func, fixtures.containers(containers=containers)
        ):
            cnt = RunningContainers()
        web_service = cnt.get_service("web")
        with mock.patch(
            "restic_compose_backup.config.config.exclude_bind_mounts", True
        ):
            mounts = web_service.filter_mounts()
        self.assertEqual(len(mounts), 1)
        self.assertEqual(mounts[0].source, "web_data")

    def test_exclude_does_not_resurrect_bind(self):
        """stack-back.volumes.exclude never resurrects a bind under EXCLUDE_BIND_MOUNTS."""
        containers = self.createContainers()
        containers += [
            {
                "service": "web",
                "labels": {
                    "stack-back.volumes": True,
                    "stack-back.volumes.exclude": "stuff",
                },
                "mounts": [
                    {
                        "Source": "/srv/files/data",
                        "Destination": "/srv/data",
                        "Type": "bind",
                    }
                ],
            },
        ]
        with mock.patch(
            list_containers_func, fixtures.containers(containers=containers)
        ):
            cnt = RunningContainers()
        web_service = cnt.get_service("web")
        with mock.patch(
            "restic_compose_backup.config.config.exclude_bind_mounts", True
        ):
            self.assertEqual(len(web_service.filter_mounts()), 0)

    def test_resurrected_bind_logged_at_info(self):
        """A bind kept only because of include is logged at INFO."""
        containers = self.createContainers()
        containers += [
            {
                "service": "web",
                "labels": {
                    "stack-back.volumes": True,
                    "stack-back.volumes.include": "data",
                },
                "mounts": [
                    {
                        "Source": "/srv/files/data",
                        "Destination": "/srv/data",
                        "Type": "bind",
                    }
                ],
            },
        ]
        with mock.patch(
            list_containers_func, fixtures.containers(containers=containers)
        ):
            cnt = RunningContainers()
        web_service = cnt.get_service("web")
        with mock.patch(
            "restic_compose_backup.config.config.exclude_bind_mounts", True
        ):
            with self.assertLogs(
                "restic_compose_backup.containers", level="INFO"
            ) as cm:
                web_service.filter_mounts()
        self.assertTrue(
            any("despite EXCLUDE_BIND_MOUNTS" in msg for msg in cm.output),
            f"Expected INFO log about resurrected bind, got: {cm.output}",
        )
