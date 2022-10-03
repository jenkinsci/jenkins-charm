# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for jenkins agents."""

import asyncio

import jenkins
from ops.model import Application, ActiveStatus
from packaging import version
import pytest
import pytest_asyncio
from pytest_operator.plugin import OpsTest

pytestmark = pytest.mark.agent


async def install_jenkins_version(
    ops_test: OpsTest, app: Application, jenkins_version: str
) -> None:
    """Install a specific version of Jenkins into the charm.

    Args:
        ops_test: pytest operator reference to the test environment.
        app: The charm running Jenkins.
        jenkins_version: The version of Jenkins to install in the charm.

    """
    # Install dependencies
    action = await app.units[0].run_action("install-dependencies", jenkins_version=jenkins_version)
    await action.wait()
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)

    # Install specified Jenkins version
    await app.units[0].ssh(
        "sudo apt-get install -y --allow-downgrades jenkins={}".format(jenkins_version)
    )
    apt_cache_output = await app.units[0].ssh("apt-cache policy jenkins")
    assert "Installed: {}".format(jenkins_version) in apt_cache_output

    # Restart Jenkins
    await app.units[0].ssh("sudo systemctl restart jenkins")


@pytest_asyncio.fixture(
    scope="module",
    params=[
        pytest.param(None, id="latest LTS jenkins version"),
        # The following are the versions of Jenkins running in production in Canonical as of
        # 2022-09-21
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
async def app_jenkins_version(
    ops_test: OpsTest, app: Application, request: pytest.FixtureRequest, series: str
):
    """Install a range of jenkins versions to run the tests against."""
    jenkins_version = request.param
    if jenkins_version:
        # Skip anything higher than 2.346 if the series is xenial
        parsed_jenkins_version = version.Version(jenkins_version)
        if series == "xenial" and parsed_jenkins_version.minor > 346:
            pytest.skip()

        await install_jenkins_version(ops_test=ops_test, app=app, jenkins_version=jenkins_version)

    yield app


@pytest_asyncio.fixture(scope="function")
async def agent(ops_test: OpsTest, series: str):
    """Deploy machine agent and destroy it after tests complete."""
    agent_app_name = "jenkins-slave"
    # Agent currently does not support xenial
    agent: Application = await ops_test.model.deploy(
        agent_app_name, series=series if series != "xenial" else "bionic", channel="edge"
    )
    # Don't wait for active because the agent will start blocked
    await ops_test.model.wait_for_idle()

    yield agent

    await agent.remove()
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


@pytest_asyncio.fixture(scope="function")
async def agent_related_to_jenkins(
    app_name: str, ops_test: OpsTest, agent: Application, app_jenkins_version: Application
):
    """Relate agent to Jenkins."""
    server_provides = "{}:master".format(app_name)
    agent_provides = "jenkins-slave:slave"
    await ops_test.model.add_relation(server_provides, agent_provides)
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)

    yield agent

    await ops_test.juju("remove-relation", server_provides, agent_provides)


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_agent_relation(
    app_jenkins_version: Application,
    agent_related_to_jenkins: Application,
    jenkins_cli: jenkins.Jenkins,
):
    """
    arrange: given jenkins that is running which is related to a running agent
    act: when the jenkins agents are queried
    assert: then the jenkins agent is included in the list and is online.
    """
    nodes_offline_status = {node["name"]: node["offline"] for node in jenkins_cli.get_nodes()}

    entity_id = agent_related_to_jenkins.units[0].entity_id.replace("/", "-")
    assert entity_id in nodes_offline_status
    assert not nodes_offline_status[entity_id], "agent did not connect to jenkins"


@pytest_asyncio.fixture(scope="function")
async def app_jenkins_version_2_150(ops_test: OpsTest, app: Application):
    """Install Jenkins version 2.150."""
    await install_jenkins_version(ops_test=ops_test, app=app, jenkins_version="2.150.3")
    yield app


@pytest_asyncio.fixture(scope="function")
async def agent_downloading_jnlp_file_related_to_jenkins(
    ops_test: OpsTest,
    app_name: str,
    agent: Application,
    app_jenkins_version_2_150: Application,
):
    """Configure agent to download the JNLP file and relate it to Jenkins."""
    # Configure the agent to download the JNLP file, Juju seems to want a string value even though
    # the configuration type is a boolean
    await agent.set_config({"download_jnlp_file": str(True)})

    # Relate to Jenkins
    await ops_test.model.add_relation("{}:master".format(app_name), "jenkins-slave:slave")
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)

    yield agent


# Even Jenkins version 2.150 does not allow the downloading of the JNLP file so expecting failure
# This test should be removed when the JNLP download configuration is removed from the machine agent charm
@pytest.mark.xfail
@pytest.mark.asyncio
async def test_agent_relation_download_jnlp(
    app_jenkins_version_2_150: Application,
    agent_downloading_jnlp_file_related_to_jenkins: Application,
    jenkins_cli: jenkins.Jenkins,
):
    """
    arrange: given jenkins that is running which is related to a running agent which downloads the
        JNLP file
    act: when the jenkins agents are queried
    assert: then the jenkins agent is included in the list and is online.
    """
    nodes_offline_status = {node["name"]: node["offline"] for node in jenkins_cli.get_nodes()}

    entity_id = agent_downloading_jnlp_file_related_to_jenkins.units[0].entity_id.replace("/", "-")
    assert entity_id in nodes_offline_status
    assert not nodes_offline_status[entity_id], "agent did not connect to jenkins"
