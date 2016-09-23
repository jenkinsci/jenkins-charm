from fixtures import TempDir

from charmfixtures import CharmTest

from charmhelpers.core import hookenv

from stubs.templating import TemplatingStub

from charms.layer.jenkins import paths
from charms.layer.jenkins.configuration import Configuration


class ConfigurationTest(CharmTest):

    def setUp(self):
        super(ConfigurationTest, self).setUp()
        self.templating = TemplatingStub()

        self.configuration = Configuration(templating=self.templating)

    def test_bootstrap(self):
        """
        If it hasn't been done yet, the Jenkins configuration file gets
        generated.
        """
        self.hooktools.config["master-executors"] = 1
        self.configuration.bootstrap()
        render = self.templating.renders[0]
        self.assertEqual("jenkins-config.xml", render.source)
        self.assertEqual(paths.config_file(), render.target)
        self.assertEqual({"master_executors": 1}, render.context)
        self.assertEqual("jenkins", render.owner)
        self.assertEqual("nogroup", render.group)
        self.assertEqual("8080/TCP", self.hooktools.port[0])

    def test_bootstrap_once(self):
        """
        If it has already been generated, the Jenkins configuration will not
        be touched again.
        """
        self.hooktools.config["master-executors"] = 1
        self.configuration.bootstrap()
        self.templating.renders.pop()
        self.configuration.bootstrap()
        self.assertEqual([], self.templating.renders)

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
