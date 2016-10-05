import os

from testtools.matchers import FileContains

from charmtest import CharmTest

from charmhelpers.core import hookenv

from charms.layer.jenkins import paths
from charms.layer.jenkins.credentials import Credentials


class CredentialsTest(CharmTest):

    def setUp(self):
        super(CredentialsTest, self).setUp()
        self.filesystem.add(paths.HOME)
        self.credentials = Credentials()

    def test_username(self):
        """
        The username matches then one set in the service configuration.
        """
        self.assertEqual("admin", self.credentials.username())

    def test_password_from_config(self):
        """
        If set, the password matches the one set in the service configuration.
        """
        self.application.config["password"] = "sekret"
        self.assertEqual("sekret", self.credentials.password())

    def test_password_from_local_state(self):
        """
        If not set, the password is retrieved from the local state.
        """
        self.application.config["password"] = ""
        hookenv.config()["_generated-password"] = "aodlaod"
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
        self.assertEqual("abc", hookenv.config()["_api-token"])
        self.assertEqual("abc", self.credentials.token())
        self.assertThat(paths.admin_token(), FileContains("abc"))
        self.assertThat(paths.admin_token(), self.filesystem.hasOwner(0, 0))
        self.assertEqual(0o100600, os.stat(paths.admin_token()).st_mode)
