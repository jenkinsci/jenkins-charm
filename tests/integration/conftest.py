# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import copy
from pathlib import Path


import pytest_asyncio
import yaml
from pytest import fixture
from pytest_operator.plugin import OpsTest
from ops.model import Application
from ops.model import Application


@fixture(scope="module")
def metadata():
    """Provides charm metadata."""
    yield yaml.safe_load(Path("./metadata.yaml").read_text())


@fixture(scope="module")
def app_name(metadata):
    """Provides app name from the metadata."""
    yield metadata["name"]


@pytest_asyncio.fixture(scope="module")
async def app(ops_test: OpsTest, app_name: str):
    """Jenkins charm used for integration testing.
    Builds the charm and deploys the charm.
    """
    charm = await ops_test.build_charm(".")
    application = await ops_test.model.deploy(
        charm, application_name=app_name, series="focal"
    )
    await ops_test.model.wait_for_idle()

    yield application
