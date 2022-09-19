# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for jenkins website."""

import secrets

import requests
import pytest
import pytest_asyncio
from pytest_operator.plugin import OpsTest
from ops.model import Application, ActiveStatus


@pytest_asyncio.fixture(scope="module")
async def cwr(app_name: str, ops_test: OpsTest, app: Application):
    """Add relationship with cwr to app."""
    # Tried to use ops_test.model.deploy with "cwr" and "cs:~juju-solutions/cwr-11" but these
    # commands fail, reverting to juju command
    await ops_test.juju("deploy cs:~juju-solutions/cwr-11")
    await ops_test.model.add_relation("{}:extension".format(app_name), "cwr:jenkins")
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)
    await ops_test.juju("expose cwr")

    yield


@pytest.mark.skip
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_cwr_ping(app: Application, cwr: Application):
    """
    arrange: given jenkins that is running which is related to a running cwr
    act: when cwr is pinged
    assert: then it returns 200.
    """
    public_address = app.units[0].public_address
    host = public_address if ":" not in public_address else "[{}]".format(public_address)
    url = "http://{}:5000/ping".format(host)
    response = requests.get(url)

    assert response.status_code == 200


@pytest.mark.skip
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_cwr_password_change(
    ops_test: OpsTest, app_restore_configuration: Application, cwr: Application
):
    """
    arrange: given jenkins that is running which is related to a running cwr
    act: when the jenkins password is changed
    assert: then cwr is still reachable.
    """
    # Check that cwr is reachable
    public_address = app_restore_configuration.units[0].public_address
    host = public_address if ":" not in public_address else "[{}]".format(public_address)
    url = "http://{}:5000/ci/v1.0/trigger/job/RunCwr".format(host)
    response = requests.get(url)

    assert response.status_code == 200

    # Change Jenkins password
    await app_restore_configuration.set_config({"password": secrets.token_urlsafe()})
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)

    # Run jub again
    response = requests.get(url)

    assert response.status_code == 200
