from testtools.matchers import (
    FileContains,
    HasPermissions,
)

from systemfixtures.matchers import HasOwnership

from charmtest import CharmTest

from charmhelpers.core import hookenv

from charms.layer.jenkins import paths
from charms.layer.jenkins.credentials import Credentials

from states import (
    INITIAL_PASSWORD,
    GENERATED_PASSWORD,
    AptInstalledJenkins,
    JenkinsConfiguredAdmin,
)


class CredentialsTest(CharmTest):

    def setUp(self):
        super(CredentialsTest, self).setUp()
        self.credentials = Credentials()

    def test_username_initial(self):
        """
        Before the initial configuration is bootstrapped, the username
        is the hard-coded 'admin'.
        """
        self.useFixture(AptInstalledJenkins(self.fakes))
        self.assertEqual("admin", self.credentials.username())

    def test_username(self):
        """
        The username matches then one set in the service configuration.
        """
        self.fakes.juju.config["username"] = "joe"
        self.useFixture(JenkinsConfiguredAdmin(self.fakes))
        self.assertEqual("joe", self.credentials.username())

    def test_password_initial(self):
        """
        Before the initial configuration is bootstrapped, the password
        is the one written by jenkins.
        """
        self.useFixture(AptInstalledJenkins(self.fakes))
        self.assertEqual(INITIAL_PASSWORD, self.credentials.password())

    def test_password_from_config(self):
        """
        If set, the password matches the one set in the service configuration.
        """
        self.fakes.juju.config["password"] = "sekret"
        self.useFixture(JenkinsConfiguredAdmin(self.fakes))
        self.assertEqual("sekret", self.credentials.password())

    def test_password_from_local_state(self):
        """
        If not set, the password is retrieved from the local state.
        """
        self.useFixture(JenkinsConfiguredAdmin(self.fakes))
        self.assertEqual(GENERATED_PASSWORD, self.credentials.password())

    def test_token(self):
        """
        The user's API token is initially None.
        """
        self.useFixture(JenkinsConfiguredAdmin(self.fakes))
        self.assertIsNone(self.credentials.token())

    def test_token_set(self):
        """
        The user's API token can be set, and will be saved in the local
        state.
        """
        self.useFixture(JenkinsConfiguredAdmin(self.fakes))
        self.assertEqual("abc", self.credentials.token("abc"))
        self.assertEqual("abc", hookenv.config()["_api-token"])
        self.assertEqual("abc", self.credentials.token())
        self.assertThat(paths.ADMIN_TOKEN, FileContains("abc"))
        self.assertThat(paths.ADMIN_TOKEN, HasOwnership(0, 0))
        self.assertThat(paths.ADMIN_TOKEN, HasPermissions("0600"))
