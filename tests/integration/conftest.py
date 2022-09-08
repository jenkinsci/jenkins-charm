# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import copy
from pathlib import Path


import pytest
import pytest_asyncio
import yaml
from pytest import fixture
from pytest_operator.plugin import OpsTest
from ops.model import Application
from ops.model import Application
import jenkins

from .types import JenkinsCredentials


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
    # Jenkins takes a while to install, setting timeout to 30 minutes
    await ops_test.model.wait_for_idle(timeout=30 * 60)

    yield application


@pytest_asyncio.fixture(scope="module")
async def app_with_groovy(ops_test: OpsTest, app: Application):
    """Add a groovy plugins to jenkins."""
    original_config = await app.get_config()
    new_config = copy.deepcopy(original_config)
    new_config["plugins"] = "groovy"
    await app.set_config(new_config)
    await ops_test.model.wait_for_idle()

    yield app

    # Revert to previous config
    await app.set_config(original_config)
    await ops_test.model.wait_for_idle()


@pytest_asyncio.fixture(scope="module")
async def jenkins_credentials(app: Application):
    """Get the jenkins credentials."""
    admin_credentials_action = await app.units[0].run_action("get-admin-credentials")
    await admin_credentials_action.wait()

    return JenkinsCredentials(
        username=admin_credentials_action.results["username"],
        password=admin_credentials_action.results["password"],
    )


@pytest_asyncio.fixture(scope="module")
async def jenkins_cli(app: Application, jenkins_credentials: JenkinsCredentials):
    """Create a CLI to jenkins."""
    url = f"http://{app.units[0].public_address}:8080"
    return jenkins.Jenkins(
        url=url,
        username=jenkins_credentials.username,
        password=jenkins_credentials.password,
    )
