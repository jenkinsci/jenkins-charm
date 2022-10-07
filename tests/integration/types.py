# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Useful types for integration tests."""

import typing


class JenkinsCredentials(typing.NamedTuple):
    """Credentials for Jenkins."""

    username: str
    password: str
