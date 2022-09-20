# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for jenkins agents."""

import asyncio

import pytest
import pytest_asyncio
from pytest_operator.plugin import OpsTest
from ops.model import Application, ActiveStatus
import jenkins


@pytest_asyncio.fixture(
    scope="module",
    params=[
        pytest.param(None, id="latest LTS jenkins version"),
        pytest.param("2.361.1", id="jenkins version 2.361"),
        pytest.param("2.346.3", id="jenkins version 2.346"),
        pytest.param("2.332.4", id="jenkins version 2.332"),
        pytest.param("2.277.4", id="jenkins version 2.277"),
        pytest.param("2.263.4", id="jenkins version 2.263"),
        pytest.param("2.249.3", id="jenkins version 2.249"),
        pytest.param("2.235.5", id="jenkins version 2.235"),
        pytest.param("2.222.4", id="jenkins version 2.222"),
        pytest.param("2.176.4", id="jenkins version 2.176"),
        pytest.param("2.150.3", id="jenkins version 2.150"),
    ],
)
async def app_jenkins_version(ops_test: OpsTest, app: Application, request: pytest.FixtureRequest):
    """Install a range of jenkins versions to run the tests against."""
    jenkins_version = request.param
    if jenkins_version:
        # Install dependencies
        action = await app.units[0].run_action(
            "install-dependencies", jenkins_version=jenkins_version
        )
        await action.wait()
        await ops_test.model.wait_for_idle(status=ActiveStatus.name)

        await app.units[0].ssh(
            "sudo apt-get install -y --allow-downgrades jenkins={}".format(jenkins_version)
        )

        apt_cache_output = await app.units[0].ssh("apt-cache policy jenkins")
        assert "Installed: {}".format(jenkins_version) in apt_cache_output

        # Restart Jenkins
        await app.units[0].ssh("sudo systemctl restart jenkins")

    yield app


@pytest_asyncio.fixture(scope="module")
async def agent(app_name: str, ops_test: OpsTest, app_jenkins_version: Application):
    """Add relationship with agent to app."""
    agent_app: Application = await ops_test.model.deploy(
        "/home/jdkandersson/src/jenkins-agent-charm/jenkins-slave_ubuntu-16.04-amd64_ubuntu-18.04-amd64_ubuntu-20.04-amd64.charm",
        series="focal",
    )
    # Don't wait for active because the agent will start blocked
    await ops_test.model.wait_for_idle()
    await ops_test.model.add_relation("{}:master".format(app_name), "jenkins-slave:slave")
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)

    yield agent_app

    await agent_app.remove()
    # Wait for machine to be de-provisioned, wait_for_idle doesn't work here because the machine
    # goes missing and wait_for_idle never stops waiting

    async def application_count():
        """Count the number of applications in the model."""
        return len((await ops_test.model.get_status()).applications)

    for _ in range(120):
        if await application_count() == 1:
            break
        await asyncio.sleep(1)
    assert await application_count() == 1, "jenkins agent failed to be removed"


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_agent_relation(
    app_jenkins_version: Application, agent: Application, jenkins_cli: jenkins.Jenkins
):
    """
    arrange: given jenkins that is running which is related to a running agent
    act: when the jenkins agents are queried
    assert: then the jenkins agent is included in the list.
    """
    nodes_offline_status = {node["name"]: node["offline"] for node in jenkins_cli.get_nodes()}

    entity_id = agent.units[0].entity_id.replace("/", "-")
    assert entity_id in nodes_offline_status
    assert not nodes_offline_status[entity_id], "agent did not connect to jenkins"
