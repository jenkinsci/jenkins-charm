# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import re
import pathlib
import pytest
from ops.model import ActiveStatus, Application

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
async def test_groovy_plugin_installed(app: Application):
    """
    arrange: given charm has been deployed and is idle
    act: when the plguins directory is checked for the groovy plugin
    assert: then it exists and its directory is not empty
    """
    stat_output = await app.units[0].ssh(f"stat {PLUGINS_DIR / 'groovy'}")

    assert "No such file or directory" not in stat_output, "Failed to locate plugin"
    # Get the size of the directory
    size_regex = r"Size: (\d+)"
    match = re.search(size_regex, stat_output)
    assert match is not None, "stat did not return Size"
    size = int(match.group(1))
    assert size > 0, "Failed to locate plugin"
