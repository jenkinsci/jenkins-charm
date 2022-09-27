# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for all tests."""

from pytest import Parser


def pytest_addoption(parser: Parser):
    """Store command line options."""
    parser.addoption("--agent-charm", action="store")
