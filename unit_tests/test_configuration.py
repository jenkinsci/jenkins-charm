from testtools.testcase import TestCase

from fixtures import (
    EnvironmentVariable,
    TempDir,
)

from stubs.hookenv import HookenvStub
from stubs.templating import TemplatingStub

from configuration import (
    CONFIG_FILE,
    Configuration,
)


class ConfigurationTest(TestCase):

    def setUp(self):
        super(ConfigurationTest, self).setUp()
        self.charm_dir = self.useFixture(TempDir())
        self.useFixture(EnvironmentVariable("CHARM_DIR", self.charm_dir.path))
        self.hookenv = HookenvStub(self.charm_dir.path)
        self.templating = TemplatingStub()

        self.configuration = Configuration(
            hookenv=self.hookenv, templating=self.templating)

    def test_bootstrap(self):
        """
        If it hasn't been done yet, the Jenkins configuration file gets
        generated.
        """
        self.hookenv.config()["master-executors"] = 1
        self.configuration.bootstrap()
        render = self.templating.renders[0]
        self.assertEqual("jenkins-config.xml", render.source)
        self.assertEqual(CONFIG_FILE, render.target)
        self.assertEqual({"master_executors": 1}, render.context)
        self.assertEqual("jenkins", render.owner)
        self.assertEqual("nogroup", render.group)
        self.assertEqual(8080, self.hookenv.port)

    def test_bootstrap_once(self):
        """
        If it has already been generated, the Jenkins configuration will not
        be touched again.
        """
        self.hookenv.config()["master-executors"] = 1
        self.configuration.bootstrap()
        self.templating.renders.pop()
        self.configuration.bootstrap()
        self.assertEqual([], self.templating.renders)
