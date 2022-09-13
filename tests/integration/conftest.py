# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

from pathlib import Path

import jenkins
from ops.model import Application, ActiveStatus
import pytest_asyncio
from pytest import fixture
from pytest_operator.plugin import OpsTest
import yaml

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
    application = await ops_test.model.deploy(charm, application_name=app_name, series="focal")
    # Jenkins takes a while to install, setting timeout to 30 minutes
    await ops_test.model.wait_for_idle(timeout=30 * 60, status=ActiveStatus.name)

    yield application


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
async def jenkins_url(app: Application):
    """Get the jenkins url."""
    public_address = app.units[0].public_address
    # Calculate host ensuring IPv6 support
    host = public_address if ":" not in public_address else "[{}]".format(public_address)
    return "http://{}:8080".format(host)


@pytest_asyncio.fixture(scope="function")
async def jenkins_cli(app: Application, jenkins_credentials: JenkinsCredentials, jenkins_url: str):
    """Create a CLI to jenkins."""
    return jenkins.Jenkins(
        url=jenkins_url,
        username=jenkins_credentials.username,
        password=jenkins_credentials.password,
    )


@pytest_asyncio.fixture(scope="function")
async def app_restore_configuration(
    ops_test: OpsTest,
    app: Application,
    jenkins_credentials: JenkinsCredentials,
    jenkins_url: str,
):
    """Restore the original configuration after the test runs."""
    original_config = {
        key: str(value["default"]) for key, value in (await app.get_config()).items()
    }
    original_config["username"] = jenkins_credentials.username
    original_config["password"] = jenkins_credentials.password

    yield app

    # Revert to previous password and config
    await app.set_config(original_config)
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)
    # Check that connection to jenkins is working
    jenkins_cli = jenkins.Jenkins(
        url=jenkins_url,
        username=jenkins_credentials.username,
        password=jenkins_credentials.password,
    )
    assert jenkins_cli.get_whoami()["id"] == jenkins_credentials.username
