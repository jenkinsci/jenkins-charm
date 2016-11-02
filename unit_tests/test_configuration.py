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


class ConfigurationTest(CharmTest):

    def setUp(self):
        super(ConfigurationTest, self).setUp()
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
        self.assertEqual({8080}, self.fakes.juju.ports["TCP"])

    def test_migrate(self):
        """
        The legacy bootstrap flag file gets migrated to a local state flag.
        """
        with open(paths.LEGACY_BOOTSTRAP_FLAG, "w") as fd:
            fd.write("")
        self.configuration.migrate()
        self.assertThat(paths.LEGACY_BOOTSTRAP_FLAG, Not(FileExists()))
