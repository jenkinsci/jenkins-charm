# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for jenkins website."""

import jenkins
import pytest
import pytest_asyncio
import requests
from ops.model import ActiveStatus, Application
from pytest_operator.plugin import OpsTest

from .config import ProxyConfig

pytestmark = pytest.mark.website


@pytest_asyncio.fixture(scope="module")
async def haproxy(app_name: str, ops_test: OpsTest, app: Application, series: str):
    """Add relationship with haproxy to app."""
    haproxy_app: Application = await ops_test.model.deploy("haproxy", series=series)
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)
    await ops_test.model.add_relation("{}:website".format(app_name), "haproxy:reverseproxy")
    await ops_test.model.wait_for_idle(status=ActiveStatus.name)
    await haproxy_app.expose()

    yield haproxy_app


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_jenkins_website_behind_proxy(app: Application, haproxy: Application):
    """
    arrange: given jenkins that is running which is related to a running haproxy
    act: when the proxy endpoint is queried
    assert: then it returns 403.
    """
    # [2022-09-29] Can't use haproxy.units[0].public_address because haproxy only listens on the
    # IPv4 address and Juju might prefer using the IPv6 address
    hostname = await haproxy.units[0].ssh(
        "python3 -c 'import socket; print(socket.gethostbyname(socket.gethostname()))'"
    )
    url = "http://{}/".format(hostname.strip())
    response = requests.get(url, timeout=60)

    assert response.status_code == 403
    assert "Authentication required" in response.text


@pytest.mark.asyncio
async def test_jenkins_proxy_configuration(
    jenkins_url: str, jenkins_cli: jenkins.Jenkins, proxy_config: ProxyConfig
):
    """
    arrange: given jenkins running with proxy configuration
    act: when the jenkins advanced configuration page is fetched
    assert: the proxy settings are configured
    """
    r = requests.Request("GET", f"{jenkins_url}/manage/pluginManager/advanced")
    res = jenkins_cli.jenkins_request(r)

    advanced_page = str(res.content, encoding="utf-8")
    assert proxy_config.proxy_hostname in advanced_page
    assert proxy_config.proxy_password not in advanced_page
    assert str(proxy_config.proxy_port) in advanced_page
    assert proxy_config.no_proxy in advanced_page
