import os

from fixtures import TempDir

from charmtest import CharmTest

from charmhelpers.core import hookenv

from charms.layer.jenkins import paths
from charms.layer.jenkins.configuration import Configuration


class ConfigurationTest(CharmTest):

    def setUp(self):
        super(ConfigurationTest, self).setUp()
        self.templates_dir = os.path.join(hookenv.charm_dir(), "templates")
        root_dir = os.path.dirname(os.path.dirname(__file__))
        os.symlink(os.path.join(root_dir, "templates"), self.templates_dir)
        self.users.add("jenkins", 123)
        self.groups.add("nogroup", 456)

        self.configuration = Configuration()

    def test_bootstrap(self):
        """
        If it hasn't been done yet, the Jenkins configuration file gets
        generated.
        """
        self.application.config["master-executors"] = 1
        self.configuration.bootstrap()
        path = paths.config_file()
        self.assertEqual(123, self.filesystem.uid[path])
        self.assertEqual(456, self.filesystem.gid[path])
        with open(path) as fd:
            self.assertIn("<numExecutors>1</numExecutors>", fd.read())
        self.assertEqual({8080}, self.unit.ports["TCP"])

    def test_bootstrap_once(self):
        """
        If it has already been generated, the Jenkins configuration will not
        be touched again.
        """
        self.application.config["master-executors"] = 1
        self.configuration.bootstrap()
        path = paths.config_file()
        stat = os.stat(path)
        self.configuration.bootstrap()
        self.assertEqual(stat, os.stat(path))
        self.assertEqual(
            "INFO: Jenkins was already configured, skipping",
            self.unit.log[-1])

    def test_migrate(self):
        """
        The legacy bootstrap flag file gets migrated to a local state flag.
        """
        jenkins_home = self.useFixture(TempDir())
        self.configuration._legacy_bootstrap_flag = jenkins_home.join("flag")
        with open(self.configuration._legacy_bootstrap_flag, "w"):
            pass
        self.configuration.migrate()
        self.assertTrue(hookenv.config()["_config-bootstrapped"])
