import os

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


class ConfigurationTest(CharmTest):

    def setUp(self):
        super(ConfigurationTest, self).setUp()
        self.fakes.users.add("jenkins", 123)
        self.fakes.groups.add("jenkins", 123)
        self.useFixture(AptInstalledJenkins(self.fakes))
        self.configuration = Configuration()

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

    def test_set_prefix1(self):
        # Case #1 - no previous config, no prefix, no change
        updated = self.configuration._set_prefix("")
        self.assertFalse(updated)

    def test_set_prefix2(self):
        # Case #2 - no previous config, a prefix, expected change
        updated = self.configuration._set_prefix("/jenkins")
        self.assertTrue(updated)

    def test_set_prefix3(self):
        # Case #3 - previous config, same prefix, no expected change
        self.configuration._set_prefix("/jenkins")
        updated = self.configuration._set_prefix("/jenkins")
        self.assertFalse(updated)

    def test_set_prefix4(self):
        # Case #4 - previous config, different prefix, expected change
        self.configuration._set_prefix("/jenkins")
        updated = self.configuration._set_prefix("/jenkins-alt")
        self.assertTrue(updated)

    def test_set_prefix5(self):
        # Case #5 - previous config, no prefix, expected change
        self.configuration._set_prefix("/jenkins")
        updated = self.configuration._set_prefix("")
        self.assertTrue(updated)

    def test_set_prefix6(self):
        # Case #6 - no config file, no expected change
        os.remove(paths.DEFAULTS_CONFIG_FILE)
        updated = self.configuration._set_prefix("/nothing")
        self.assertFalse(updated)

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
        needs_restart = self.configuration.set_url()
        self.assertFalse(needs_restart)
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
            print(self.fakes.juju.log)
            self.assertThat(
                ca_cert_file,
                FileContains(
                    matcher=Contains(ca_cert)))
        finally:
            hookenv.config()["update-center-ca"] = orig_update_center_ca
