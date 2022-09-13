# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for jenkins website."""

import requests
import pytest
import pytest_asyncio
from pytest_operator.plugin import OpsTest
from ops.model import Application, ActiveStatus, Relation


@pytest_asyncio.fixture(scope="module")
async def haproxy(app_name: str, ops_test: OpsTest, app: Application):
    """Add relationship with haproxy to app."""
    haproxy_app: Application = await ops_test.model.deploy("haproxy", series="focal")
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)
    relation: Relation = await ops_test.model.add_relation(
        "{}:website".format(app_name), "haproxy:reverseproxy"
    )
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)
    await haproxy_app.expose()

    yield haproxy_app

    await relation.destroy()
    await haproxy_app.remove()
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_jenkins_website_behind_proxy(app: Application, haproxy: Application):
    """
    arrange: given jenkins that is running which is related to a running haproxy
    act: when the proxy endpoint is queried
    assert: then it returns 403.
    """
    public_address = haproxy.units[0].public_address
    host = public_address if ":" not in public_address else "[{}]".format(public_address)
    url = "http://{}/".format(host)
    response = requests.get(url)

    assert response.status_code == 403
    assert "Authentication required" in response.text
