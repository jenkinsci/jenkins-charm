from fixtures import MonkeyPatch

from testtools.matchers import (
    FileContains,
    HasPermissions,
)

from systemfixtures.matchers import HasOwnership

from charmhelpers.core import hookenv

from charms.layer.jenkins import paths
from charms.layer.jenkins.users import Users
from charms.layer.jenkins.api import (
    GET_TOKEN_SCRIPT,
    UPDATE_PASSWORD_SCRIPT,
)

from testing import JenkinsTest
from states import AptInstalledJenkins


class UsersTest(JenkinsTest):

    def setUp(self):
        super(UsersTest, self).setUp()
        self.useFixture(AptInstalledJenkins(self.fakes))
        self.fakes.jenkins.scripts[GET_TOKEN_SCRIPT.format("admin")] = "abc\n"
        self.users = Users()

    def test_configure_admin_custom_password(self):
        """
        If a password is provided, it's used to configure the admin user.
        """
        config = hookenv.config()
        orig_password = config["password"]
        try:
            config["password"] = "x"

            script = UPDATE_PASSWORD_SCRIPT.format(username="admin", password="x")
            self.fakes.jenkins.scripts[script] = ""

            self.users.configure_admin()

            self.assertThat(paths.ADMIN_PASSWORD, FileContains("x"))
            self.assertThat(paths.ADMIN_PASSWORD, HasOwnership(0, 0))
            self.assertThat(paths.ADMIN_PASSWORD, HasPermissions("0600"))

            self.assertThat(paths.LAST_EXEC, FileContains("2.0.0\n"))
            self.assertThat(paths.LAST_EXEC, HasOwnership(123, 456))
        finally:
            config["password"] = orig_password

    def test_configure_admin_random_password(self):
        """
        If a password is not provided, a random one will be generated.
        """
        def pwgen(length):
            return "z"
        script = UPDATE_PASSWORD_SCRIPT.format(username="admin", password="z")
        self.fakes.jenkins.scripts[script] = ""

        self.useFixture(MonkeyPatch("charmhelpers.core.host.pwgen", pwgen))
        self.users.configure_admin()
        self.assertTrue(hookenv.config()["_generated-password"])
