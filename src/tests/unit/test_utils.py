"""Unit tests for utils"""

import os
from unittest import mock

import pytest
from docker.utils import parse_host

from restic_compose_backup import utils
from .conftest import BaseTestCase

pytestmark = pytest.mark.unit


class DockerHostFallbackTests(BaseTestCase):
    """The DOCKER_HOST fallback must set a valid socket URL"""

    def test_docker_host_fallback_is_valid_socket_url(self):
        """When DOCKER_HOST is unset, the fallback must parse to a valid unix URL

        Regression guard: the previous default ``unix://tmp/docker.sock`` parsed
        to the broken ``http+unix://tmp//docker.sock``.
        """
        saved = os.environ.pop("DOCKER_HOST", None)
        try:
            with mock.patch("restic_compose_backup.utils.docker.from_env"):
                utils.docker_client()
            parsed = parse_host(os.environ["DOCKER_HOST"])
        finally:
            if saved is None:
                os.environ.pop("DOCKER_HOST", None)
            else:
                os.environ["DOCKER_HOST"] = saved

        self.assertTrue(parsed.startswith("http+unix://"), msg=f"parsed={parsed!r}")
        # The broken URL produced '//docker.sock'; a correct one must not.
        self.assertNotIn("//docker.sock", parsed, msg=f"parsed={parsed!r}")
        self.assertIn("var/run/docker.sock", parsed, msg=f"parsed={parsed!r}")
