# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for jenkins agents."""

import pytest
import pytest_asyncio
from pytest_operator.plugin import OpsTest
from ops.model import Application, ActiveStatus


NRPE_CHECK_HTTP_FILE = "/usr/lib/nagios/plugins/check_http"
NRPE_CONFIG_FILE = "/etc/nagios/nrpe.d/check_jenkins_http.cfg"
NAGIOS_CMD = "sudo -u nagios $(grep -e '{}' {} | cut -d'=' -f2-)".format(
    NRPE_CHECK_HTTP_FILE, NRPE_CONFIG_FILE
)


@pytest_asyncio.fixture(scope="module")
async def nrpe(app_name: str, ops_test: OpsTest, app: Application):
    """Add relationship with nrpe to app."""
    nrpe_app: Application = await ops_test.model.deploy("nrpe", series="focal")
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)
    await ops_test.model.add_relation(
        "{}:nrpe-external-master".format(app_name), "nrpe:nrpe-external-master"
    )
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

    assert "PLACEHOLDER" in nagios_output, "ngre not installed"


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

    assert "PLACEHOLDER" in nagios_output, "ngre not working after Jenkins URL change"
