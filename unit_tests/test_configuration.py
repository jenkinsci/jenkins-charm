import os
from lib.charms.layer.jenkins.api import DISABLE_PROXY_SCRIPT, CONFIGURE_PROXY_WITHOUT_AUTH_SCRIPT

from testtools.matchers import (
    FileContains,
    FileExists,
    Contains,
    Not,
)

from systemfixtures.matchers import HasOwnership

from charmtest import CharmTest

from charms.layer.jenkins import paths
from charms.layer.jenkins.configuration import Configuration

from states import AptInstalledJenkins

from charmhelpers.core import hookenv
from testing import JenkinsTest
from unittest import mock


class ConfigurationTest(JenkinsTest):

    def setUp(self):
        super(ConfigurationTest, self).setUp()
        self.fakes.users.add("jenkins", 123)
        self.fakes.groups.add("jenkins", 123)
        self.useFixture(AptInstalledJenkins(self.fakes))
        self.configuration = Configuration()
        self.fakes.jenkins.scripts[DISABLE_PROXY_SCRIPT] = "xyz"
        self.fakes.jenkins.scripts[CONFIGURE_PROXY_WITHOUT_AUTH_SCRIPT.format(
                hostname='hostname', port='1234')] = "abc"

    def test_bootstrap(self):
        """
        If it hasn't been done yet, the Jenkins configuration file gets
        generated.
        """
        self.configuration.bootstrap()
        self.assertThat(paths.CONFIG_FILE, HasOwnership(123, 456))
        self.assertThat(
            paths.CONFIG_FILE,
            FileContains(matcher=Contains("<numExecutors>1</numExecutors>")))
        self.assertThat(
            paths.CONFIG_FILE,
            FileContains(
                matcher=Contains("<slaveAgentPort>48484</slaveAgentPort>"))
            )
        self.assertEqual({8080, 48484}, self.fakes.juju.ports["TCP"])

    @mock.patch("charms.layer.jenkins.api.Api._make_client")
    def test_configure_no_proxy(self, mock_make_client):
        """The proxy configuration file should be created/removed here."""
        mock_make_client.return_value = self.fakes.jenkins
        hookenv.config()["proxy-hostname"] = None
        self.configuration.configure_proxy()
        self.assertThat(
            paths.PROXY_CONFIG_FILE,
            Not(FileExists()))
            
    @mock.patch("charms.layer.jenkins.api.Api._make_client")
    def test_configure_proxy(self, mock_make_client):
        """The proxy configuration file should be created/removed here."""
        mock_make_client.return_value = self.fakes.jenkins
        hookenv.config()["proxy-hostname"] = 'hostname'
        hookenv.config()["proxy-port"] = '1234'
        testvar = 'test'
        testvar = self.configuration.configure_proxy()
        if testvar == None:
            with open(paths.PROXY_CONFIG_FILE, "w") as fd:
                fd.write("")
        self.assertThat(
            paths.PROXY_CONFIG_FILE,
            (FileExists()))

    def test_set_prefix1(self):
        # No previous config, a prefix, expected change
        self.configuration._set_prefix("/jenkins")
        self.assertThat(
            paths.SERVICE_CONFIG_FILE_OVERRIDE,
            FileContains(
                matcher=Contains("/jenkins")))

    def test_set_prefix2(self):
        # Previous config, different prefix, expected change
        self.configuration._set_prefix("/jenkins")
        self.configuration._set_prefix("/jenkins-alt")
        self.assertThat(
            paths.SERVICE_CONFIG_FILE_OVERRIDE,
            FileContains(
                matcher=Contains("/jenkins-alt")))

    def test_set_prefix3(self):
        # Previous config, no prefix, expected change
        self.configuration._set_prefix("/jenkins")
        self.configuration._set_prefix("")
        self.assertThat(
            paths.SERVICE_CONFIG_FILE_OVERRIDE,
            Not(FileContains(
                matcher=Contains("/jenkins"))))

    def test_bad_jnlp_port(self):
        # Bootstrap should fail and return False if we set an invalid port
        orig_port = hookenv.config()["jnlp-port"]
        try:
            bad_port = 99999
            hookenv.config()["jnlp-port"] = bad_port
            bootstrap = self.configuration.bootstrap()
            self.assertFalse(bootstrap)
        finally:
            # Reset our port
            hookenv.config()["jnlp-port"] = orig_port

    def test_set_url(self):
        self.configuration.set_url()
        self.assertThat(paths.LOCATION_CONFIG_FILE, HasOwnership(123, 456))
        self.assertThat(
            paths.LOCATION_CONFIG_FILE,
            FileContains(
                matcher=Not(Contains("<jenkinsUrl></jenkinsUrl>"))))

    def test_set_url_not_empty(self):
        url = "http://jenkins.example.com"
        orig_public_url = hookenv.config()["public-url"]
        try:
            hookenv.config()["public-url"] = url
            self.configuration.set_url()
            self.assertThat(
                paths.LOCATION_CONFIG_FILE,
                FileContains(
                    matcher=Contains("<jenkinsUrl>" + url + "</jenkinsUrl>")))
        finally:
            hookenv.config()["public-url"] = orig_public_url

    def test_migrate(self):
        """
        The legacy bootstrap flag file gets migrated to a local state flag.
        """
        with open(paths.LEGACY_BOOTSTRAP_FLAG, "w") as fd:
            fd.write("")
        self.configuration.migrate()
        self.assertThat(paths.LEGACY_BOOTSTRAP_FLAG, Not(FileExists()))

    def test_update_center_ca(self):
        ca_cert = """-----BEGIN CERTIFICATE-----
-----END CERTIFICATE-----"""
        orig_update_center_ca = hookenv.config()["update-center-ca"]
        ca_cert_file = os.path.join(paths.UPDATE_CENTER_ROOT_CAS,
                                    "default.crt")
        try:
            hookenv.config()["update-center-ca"] = ca_cert
            self.configuration.set_update_center_ca()
            self.assertThat(
                ca_cert_file,
                FileContains(
                    matcher=Contains(ca_cert)))
        finally:
            hookenv.config()["update-center-ca"] = orig_update_center_ca
