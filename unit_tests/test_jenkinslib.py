from fixtures import TestWithFixtures, EnvironmentVariable, TempDir

from charmhelpers.core.hookenv import Config

from jenkinslib import Jenkins


class ExecdStub(object):
    """Testable stub for the charms.layer.execd module from the basic layer."""

    def execd_preinstall(self, execd_dir=None):
        self.preinstall_dir = execd_dir


class HookenvStub(object):
    """Testable stub for charmhelpers.core.hookenv."""

    def __init__(self):
        # We should disable implicit saving since it runs at charm exit using
        # globals :(
        self._config = Config()
        #self._config.implicit_save = False

    def config(self):
        return self._config


class JenkinsTest(TestWithFixtures):

    def setUp(self):
        super(JenkinsTest, self).setUp()
        # XXX The charmhelpers.core.hookenv.Config class grabs its path from
        #     the environment, so it's not very test-friendly. Should be fixed
        #     upstream.
        charm_dir = self.useFixture(TempDir())
        self.useFixture(EnvironmentVariable("CHARM_DIR", charm_dir.path))

        self.execd = ExecdStub()
        self.hookenv = HookenvStub()
        self.jenkins = Jenkins(execd=self.execd)

    def test_custom_preinstall_dir(self):
        """
        The legacy hooks/install.d pre-install directory is still supported.
        """
        self.jenkins.install()
        self.assertEqual("hooks/install.d", self.execd.preinstall_dir)
