# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for basic Jenkins functionality."""

import secrets

from ops.model import ActiveStatus, Application
import pytest

from pytest_operator.plugin import OpsTest
import jenkins

from .types import JenkinsCredentials
from .config import PLUGINS_DIR


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_active(app: Application):
    """
    arrange: given charm has been deployed and is idle
    act: when the status is checked
    assert: then the status is active and a message which contains running has been set
    """
    assert app.units[0].workload_status == ActiveStatus.name
    assert "running" in app.units[0].workload_status_message


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_debian_stable_in_sources(app: Application):
    """
    arrange: given charm has been deployed and is idle
    act: when /etc/apt/sources.list is checked
    assert: then it contains debian-stable
    """
    souces_list_contents = await app.units[0].ssh("cat /etc/apt/sources.list")

    assert "debian-stable" in souces_list_contents, "LTS not in sources.list"


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_tools_installed(app: Application):
    """
    arrange: given charm has been deployed and is idle
    act: when checking for the python3-testtools package
    assert: then it is found
    """
    dpkg_output = await app.units[0].ssh("dpkg -l python3-testtools")

    # Check for ii in the output which indicates that the queried package is installed
    assert "ii" in dpkg_output, "No tool installation found"


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_jenkins_user_exists(app: Application):
    """
    arrange: given charm has been deployed and is idle
    act: when the existence of the jenkins user is checked
    assert: then it is found
    """
    id_output = await app.units[0].ssh("id -u jenkins")

    assert "no such user" not in id_output, "No Jenkins system user"


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_jenkins_service_running(app: Application):
    """
    arrange: given charm has been deployed and is idle
    act: when the jenkins service is checked for
    assert: then it is running
    """
    service_output = await app.units[0].ssh("service jenkins status")

    assert "active (running)" in service_output, "No Jenkins Service Running"


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_jenkins_cli_whoami(
    jenkins_cli: jenkins.Jenkins, jenkins_credentials: JenkinsCredentials
):
    """
    arrange: given jenkins CLI that is connected to the running Jenkins server
    act: when get_whoami is run
    assert: then admin user is returned.
    """
    user = jenkins_cli.get_whoami()

    assert user["id"] == jenkins_credentials.username


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_groovy_installed(ops_test: OpsTest, app_restore_configuration: Application):
    """
    arrange: given charm has been deployed
    act: when the groovy plugin is added to the configuration
    assert: then the .jpi files for the plugin is found in the plugins directory.
    """
    await app_restore_configuration.set_config({"plugins": "groovy"})
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)

    find_output = await app_restore_configuration.units[0].ssh("find {}".format(PLUGINS_DIR))

    assert "groovy.jpi" in find_output, "Failed to locate groovy"


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_plugins_cleaned(ops_test: OpsTest, app_restore_configuration: Application):
    """
    arrange: given charm has been deployed
    act: when the groovy plugin is added to the configuration and then removed and
        remove-unlisted-plugins is set
    assert: then the .jpi files for the plugin is found on adding it initially and then not found
        after it has been removed in the plugins directory.
    """
    # Add groovy initially
    await app_restore_configuration.set_config({"plugins": "groovy"})
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)

    find_command = "find {}".format(PLUGINS_DIR)
    find_output = await app_restore_configuration.units[0].ssh(find_command)

    groovy_plugin_file = "groovy.jpi"
    assert groovy_plugin_file in find_output, "Failed to locate groovy after install"

    # Remove groovy and set remove-unlisted-plugins
    await app_restore_configuration.set_config({"plugins": "", "remove-unlisted-plugins": "yes"})
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)

    find_output = await app_restore_configuration.units[0].ssh(find_command)

    assert (
        groovy_plugin_file not in find_output
    ), "groovy still present after removed from configuration and remove-unlisted-plugins is set"


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_jenkins_cli_whoami_password_change(
    ops_test: OpsTest,
    app_restore_configuration: Application,
    jenkins_credentials: JenkinsCredentials,
    jenkins_url: str,
):
    """
    arrange: given jenkins that is running
    act: when the password is changed via configuration and get_whoami is run with the new password
    assert: then admin user is returned.
    """
    new_password = secrets.token_urlsafe()
    await app_restore_configuration.set_config({"password": new_password})
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)
    jenkins_cli = jenkins.Jenkins(
        url=jenkins_url,
        username=jenkins_credentials.username,
        password=new_password,
    )

    user = jenkins_cli.get_whoami()

    assert user["id"] == jenkins_credentials.username


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_jenkins_cli_whoami_url_change(
    ops_test: OpsTest,
    app_restore_configuration: Application,
    jenkins_credentials: JenkinsCredentials,
    jenkins_url: str,
):
    """
    arrange: given jenkins that is running
    act: when the url is changed via configuration and get_whoami is run with the new url
    assert: then admin user is returned.
    """
    new_url = "{}/jenkins-alt".format(jenkins_url)
    await app_restore_configuration.set_config({"public-url": new_url})
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)
    jenkins_cli = jenkins.Jenkins(
        url=new_url,
        username=jenkins_credentials.username,
        password=jenkins_credentials.password,
    )

    user = jenkins_cli.get_whoami()

    assert user["id"] == jenkins_credentials.username


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_tool_change(ops_test: OpsTest, app_restore_configuration: Application):
    """
    arrange: given jenkins that is running
    act: when a new tool is added to the configuration
    assert: then the tool is installed.
    """
    await app_restore_configuration.set_config({"tools": "python3-lxml"})
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)

    dpkg_output = await app_restore_configuration.units[0].ssh("dpkg -l python3-lxml")
    # Check for ii in the output which indicates that the queried package is installed
    assert "ii" in dpkg_output, "No tool installation found"
