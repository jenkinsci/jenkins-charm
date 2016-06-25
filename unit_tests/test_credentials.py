from testtools.testcase import TestCase

from fixtures import (
    EnvironmentVariable,
    TempDir,
)

from stubs.hookenv import HookenvStub

from charms.layer.jenkins.credentials import Credentials


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

    def test_token(self):
        """
        The user's API token is initially None.
        """
        self.assertIsNone(self.credentials.token())

    def test_token_set(self):
        """
        The user's API token can be set, and will be saved in the local
        state.
        """
        self.assertEqual("abc", self.credentials.token("abc"))
        self.assertEqual("abc", self.hookenv.config()["_api-token"])
        self.assertEqual("abc", self.credentials.token())
