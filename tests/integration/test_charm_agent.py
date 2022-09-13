# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for jenkins agents."""

import pytest
import pytest_asyncio
from pytest_operator.plugin import OpsTest
from ops.model import Application, ActiveStatus, Relation
import jenkins


@pytest_asyncio.fixture(scope="module")
async def agent(app_name: str, ops_test: OpsTest, app: Application):
    """Add relationship with agent to app."""
    agent_app: Application = await ops_test.model.deploy("jenkins-slave", series="focal")
    # Don't wait for idle because the agent will start blocked
    await ops_test.model.wait_for_idle()
    relation: Relation = await ops_test.model.add_relation(
        "{}:master".format(app_name), "jenkins-slave:slave"
    )
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)

    yield agent_app

    await relation.destroy()
    await agent_app.remove()
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_agent_relation(app: Application, agent: Application, jenkins_cli: jenkins.Jenkins):
    """
    arrange: given jenkins that is running which is related to a running agent
    act: when the jenkins agents are queried
    assert: then the jenkins agent is included in the list.
    """
    nodes = jenkins_cli.get_nodes()

    assert str(agent.units[0]) in nodes
