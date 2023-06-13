# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Useful configuration for integration tests."""

import dataclasses
import pathlib

PLUGINS_DIR = pathlib.Path("/var/lib/jenkins/plugins")


@dataclasses.dataclass(frozen=True)
class ProxyConfig:
    """The Jenkins proxy configuration values."""

    proxy_hostname: str
    proxy_port: int
    proxy_username: str
    proxy_password: str
    no_proxy: str
