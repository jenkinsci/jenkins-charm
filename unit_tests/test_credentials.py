from testtools.testcase import TestCase

from fixtures import (
    EnvironmentVariable,
    TempDir,
)

from stubs.hookenv import HookenvStub

from jenkinslib.credentials import Credentials


class CredentialsTest(TestCase):

    def setUp(self):
        super(CredentialsTest, self).setUp()
        self.charm_dir = self.useFixture(TempDir())
        self.useFixture(EnvironmentVariable("CHARM_DIR", self.charm_dir.path))
        self.hookenv = HookenvStub(self.charm_dir.path)
        self.hookenv.config()["username"] = "admin"
        self.credentials = Credentials(hookenv=self.hookenv)

    def test_username(self):
        """
        The username matches then one set in the service configuration.
        """
        self.assertEqual("admin", self.credentials.username())

    def test_password_from_config(self):
        """
        If set, the password matches the one set in the service configuration.
        """
        self.hookenv.config()["password"] = "sekret"
        self.assertEqual("sekret", self.credentials.password())

    def test_password_from_local_state(self):
        """
        If not set, the password is retrieved from the local state.
        """
        self.hookenv.config()["password"] = ""
        self.hookenv.config()["_generated-password"] = "aodlaod"
        self.assertEqual("aodlaod", self.credentials.password())
