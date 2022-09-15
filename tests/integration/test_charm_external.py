# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for jenkins agents."""

import pytest
import pytest_asyncio
from pytest_operator.plugin import OpsTest
from ops.model import Application, ActiveStatus

from .config import PLUGINS_DIR


@pytest_asyncio.fixture(scope="function")
async def ci_configuration(
    app_name: str, ops_test: OpsTest, app_restore_configuration: Application
):
    """Add relationship with ci-configuration to app."""
    # Add required additional tools
    config = await app_restore_configuration.get_config()
    current_tools = config["tools"]["value"]
    # XXX ci-configuration is currently broken and needs paramiko.
    # XXX when deployed on xenial (python 2) ci-configuration needs more.
    tools = "{} python-paramiko python-yaml python-apt".format(current_tools)
    await app_restore_configuration.set_config({"tools": tools})
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)
    # Deploy ci-configurator
    ci_configurator_app: Application = await ops_test.model.deploy(
        "ci-configurator",
        series="focal",
        config={"config-repo": "lp:~free.ekanayaka/junk/ci-configurator-test-repo"},
    )
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)
    await ops_test.model.add_relation(
        "{}:extension".format(app_name), "ci-configurator:jenkins-configurator"
    )
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)

    yield ci_configurator_app


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_agent_relation(
    app_restore_configuration: Application, ci_configuration: Application
):
    """
    arrange: given jenkins that is running which is related to a running ci-configurator
    act: when the installed plugins are checked
    assert: then the required ci-configurator plugins are installed.
    """
    find_output = await app_restore_configuration.units[0].ssh("find {}".format(PLUGINS_DIR))

    assert "git.hpi" in find_output, "Failed to locate git"
    assert "git-client.hpi" in find_output, "Failed to locate git-client"
