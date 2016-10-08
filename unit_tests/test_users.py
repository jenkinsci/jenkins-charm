import os

from testtools.matchers import (
    DirExists,
    FileContains,
    Contains,
    HasPermissions,
)

from systemfixtures.matchers import HasOwnership

from charmtest import CharmTest

from charmhelpers.core import hookenv

from charms.layer.jenkins import paths
from charms.layer.jenkins.users import Users


class UsersTest(CharmTest):

    def setUp(self):
        super(UsersTest, self).setUp()
        self.fakes.fs.add(paths.HOME)
        os.makedirs(paths.HOME)
        self.fakes.users.add("jenkins", 123)
        self.fakes.groups.add("nogroup", 456)

        self.users = Users()

    def test_configure_admin_custom_password(self):
        """
        If a password is provided, it's used to configure the admin user.
        """
        self.fakes.juju.config["password"] = "sekret"
        self.users.configure_admin()
        self.assertThat(paths.ADMIN_PASSWORD, FileContains("sekret"))
        self.assertThat(paths.ADMIN_PASSWORD, HasOwnership(0, 0))
        self.assertThat(paths.ADMIN_PASSWORD, HasPermissions("0600"))

    def test_configure_admin_random_password(self):
        """
        If a password is not provided, a random one will be generated.
        """
        self.users.configure_admin()
        self.assertTrue(hookenv.config()["_generated-password"])

    def test_configure_admin_make_users_dir(self):
        """
        The Jenkins user directories are created with proper permissions.
        """
        self.users.configure_admin()

        self.assertThat(paths.USERS, DirExists())
        self.assertThat(paths.USERS, HasOwnership(123, 456))

        admin_user_dir = os.path.join(paths.USERS, "admin")
        self.assertThat(admin_user_dir, DirExists())
        self.assertThat(admin_user_dir, HasOwnership(123, 456))
        self.assertThat(paths.ADMIN_PASSWORD, HasPermissions("0600"))

    def test_configure_admin_write_user_config(self):
        """
        A Jenkins user-config.xml file is written with the appropriate
        details.
        """
        self.users.configure_admin()

        path = os.path.join(paths.USERS, "admin", "config.xml")
        self.assertThat(
            path, FileContains(matcher=Contains("<fullName>admin</fullName>")))
        self.assertThat(path, HasOwnership(123, 456))
