# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for jenkins relation with nrpe."""

import pytest
import pytest_asyncio
from pytest_operator.plugin import OpsTest
from ops.model import Application, ActiveStatus

pytestmark = pytest.mark.nrpe


NRPE_CHECK_HTTP_FILE = "/usr/lib/nagios/plugins/check_http"
NRPE_CONFIG_FILE = "/etc/nagios/nrpe.d/check_check_jenkins_http.cfg"
NAGIOS_CMD = "sudo $(grep -e '{}' {} | cut -d'=' -f2-)".format(
    NRPE_CHECK_HTTP_FILE, NRPE_CONFIG_FILE
)
NAGIOS_CMD_SUCCESS = "HTTP OK"


@pytest_asyncio.fixture(scope="module")
async def nrpe(app_name: str, ops_test: OpsTest, app: Application, series: str):
    """Add relationship with nrpe and nagios to app."""
    nrpe_app: Application = await ops_test.model.deploy("nrpe", series=series)
    await ops_test.model.add_relation(
        "{}:nrpe-external-master".format(app_name), "nrpe:nrpe-external-master"
    )
    # [2022-09-29] Nagios does not support focal
    await ops_test.model.deploy("nagios", series=(series if series != "focal" else "bionic"))
    await ops_test.model.add_relation("nrpe:monitors", "nagios:monitors")
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)

    yield nrpe_app


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_nrpe_relation(app: Application, nrpe: Application):
    """
    arrange: given jenkins that is running which is related to a running nrpe
    act: when a command is run to verify the nrpe installation
    assert: then the command exits succesfully.
    """
    nagios_output = await app.units[0].ssh(NAGIOS_CMD)

    assert NAGIOS_CMD_SUCCESS in nagios_output, "nrpe not installed"


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_nrpe_relation_url_change(
    ops_test: OpsTest, app_restore_configuration: Application, nrpe: Application, jenkins_url: str
):
    """
    arrange: given jenkins that is running which is related to a running nrpe
    act: when the jenkins URL is changed and a command is run to verify the nrpe installation
    assert: then the command exits succesfully.
    """
    new_url = "{}/jenkins-alt".format(jenkins_url)
    await app_restore_configuration.set_config({"public-url": new_url})
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)

    nagios_output = await app_restore_configuration.units[0].ssh(NAGIOS_CMD)

    assert NAGIOS_CMD_SUCCESS in nagios_output, "nrpe not working after Jenkins URL change"
