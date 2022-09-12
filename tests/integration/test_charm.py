# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import pathlib
import secrets

from ops.model import ActiveStatus, Application
import pytest

from pytest_operator.plugin import OpsTest
import jenkins

from .types import JenkinsCredentials

PLUGINS_DIR = pathlib.Path("/var/lib/jenkins/plugins")


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
async def test_groovy_installed(
    ops_test: OpsTest, app_restore_configuration: Application
):
    """
    arrange: given charm has been deployed
    act: when the groovy plugin is added to the configuration
    assert: then the .jpi files for the plugin is found in the plugins directory.
    """
    config = await app_restore_configuration.get_config()
    config["plugins"] = "groovy"
    await app_restore_configuration.set_config(config)
    await ops_test.model.wait_for_idle()

    find_output = await app_restore_configuration.units[0].ssh(
        "find {}".format(PLUGINS_DIR)
    )

    assert "groovy.jpi" in find_output, "Failed to locate groovy"


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
    config = await app_restore_configuration.get_config()
    new_password = secrets.token_urlsafe()
    config["password"] = new_password
    await app_restore_configuration.set_config(config)
    await ops_test.model.wait_for_idle()
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
    config = await app_restore_configuration.get_config()
    new_url = "{}/jenkins-alt".format(jenkins_url)
    config["public-url"] = new_url
    await app_restore_configuration.set_config(config)
    await ops_test.model.wait_for_idle()
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
    config = await app_restore_configuration.get_config()
    config["tools"] = "python3-lxml"
    await app_restore_configuration.set_config(config)
    await ops_test.model.wait_for_idle()

    dpkg_output = await app_restore_configuration.units[0].ssh("dpkg -l python3-lxml")
    assert "ii" in dpkg_output, "No tool installation found"


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_upgrade(ops_test: OpsTest, app_restore_configuration: Application):
    """
    arrange: given jenkins that is running
    act: when the configuration is changed to bundle, a previous jre and version of jenkins is
        installed and the upgrade action is run
    assert: then the the jre version is moved back to the default version and jenkins is upgraded.
    """
    # Set release to bundle to be able to trigger the upgrade action
    config = await app_restore_configuration.get_config()
    config["release"] = "bundle"
    config["bundle-site"] = "https://pkg.jenkins.io"
    await app_restore_configuration.set_config(config)
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)
    # Remove current Java and Jenkins version
    await app_restore_configuration.units[0].ssh(
        "sudo apt remove -y default-jre-headless jenkins"
    )
    # Install previous Java and Jenkins version
    jenkins_version = "2.346.1"
    await app_restore_configuration.units[0].ssh(
        "sudo apt-get install -y openjdk-8-jre-headless jenkins={}".format(
            jenkins_version
        )
    )
    # Restart and check that jenkins is running
    await app_restore_configuration.units[0].ssh("sudo systemctl restart jenkins")
    systemctl_output = await app_restore_configuration.units[0].ssh(
        "sudo systemctl status jenkins"
    )
    assert (
        "active (running)" in systemctl_output
    ), "Jenkins did not start after downgrade"
    # Check version of jenkins that is installed
    jenkins_output = await app_restore_configuration.units[0].ssh("jenkins --version")
    assert jenkins_version in jenkins_output
    # Check java version
    java_output = await app_restore_configuration.units[0].ssh("java --version")
    assert "openjdk 8." in java_output

    # Execute upgrade action
    action = await app_restore_configuration.units[0].run_action("upgrade")
    await action.wait()
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)

    # Check that jenkins is running
    systemctl_output = await app_restore_configuration.units[0].ssh(
        "sudo systemctl status jenkins"
    )
    assert "active (running)" in systemctl_output, "Jenkins did not start after upgrade"
    # Check version of jenkins that is installed
    jenkins_output = await app_restore_configuration.units[0].ssh("jenkins --version")
    assert jenkins_version not in jenkins_output
    # Check java version
    java_output = await app_restore_configuration.units[0].ssh("java --version")
    assert "openjdk 8." not in java_output
