import os

from testtools.testcase import TestCase

from fixtures import (
    EnvironmentVariable,
    TempDir,
)

from stubs.hookenv import HookenvStub
from stubs.host import HostStub
from stubs.templating import TemplatingStub

from charms.layer.jenkins.users import (
    USERS,
    PASSWORD_FILE,
    Users,
)

# SHA256 version of the hard-coded random password from HostStub.password
SALTY_PASSWORD = (
    "eegh5a:3c5eb427399cab549de5139adb70644a7c5580657f6b01f2b2f3380f0f2ce9b7")


class UsersTest(TestCase):

    def setUp(self):
        super(UsersTest, self).setUp()
        self.charm_dir = self.useFixture(TempDir())
        self.useFixture(EnvironmentVariable("CHARM_DIR", self.charm_dir.path))
        self.hookenv = HookenvStub(self.charm_dir.path)
        self.host = HostStub()
        self.templating = TemplatingStub()

        self.users = Users(
            hookenv=self.hookenv, host=self.host, templating=self.templating)

    def test_configure_admin_custom_password(self):
        """
        If a password is provided, it's used to configure the admin user.
        """
        self.hookenv.config()["master-executors"] = 1
        self.hookenv.config()["username"] = "admin"
        self.hookenv.config()["password"] = "sekret"
        self.users.configure_admin()
        [password_file] = self.host.files
        self.assertEqual(PASSWORD_FILE, password_file.path)
        self.assertEqual(b"sekret", password_file.content)
        self.assertEqual("root", password_file.owner)
        self.assertEqual("root", password_file.group)
        self.assertEqual(0o0600, password_file.perms)

    def test_configure_admin_random_password(self):
        """
        If a password is not provided, a random one will be generated.
        """
        config = self.hookenv.config()
        config["username"] = "admin"
        config["password"] = ""
        self.users.configure_admin()
        self.assertEqual(self.host.password, config["_generated-password"])

    def test_configure_admin_make_users_dir(self):
        """
        The Jenkins user directories are created with proper permissions.
        """
        self.hookenv.config()["username"] = "admin"
        self.hookenv.config()["password"] = ""
        self.users.configure_admin()
        users_dir = self.host.dirs[0]
        admin_user_dir = self.host.dirs[1]
        self.assertEqual(USERS, users_dir.path)
        self.assertEqual("jenkins", users_dir.owner)
        self.assertEqual("nogroup", users_dir.group)
        self.assertEqual(
            os.path.join(USERS, "admin"), admin_user_dir.path)
        self.assertEqual("jenkins", admin_user_dir.owner)
        self.assertEqual("nogroup", admin_user_dir.group)
        self.assertEqual(0o0700, admin_user_dir.perms)

    def test_configure_admin_write_user_config(self):
        """
        A Jenkins user-config.xml file is written with the appropriate
        details.
        """
        self.hookenv.config()["username"] = "admin"
        self.hookenv.config()["password"] = ""
        self.users.configure_admin()
        render = self.templating.renders[0]
        self.assertEqual("user-config.xml", render.source)
        self.assertEqual(
            os.path.join(USERS, "admin", "config.xml"),
            render.target)
        self.assertEqual(
            {"username": "admin", "password": SALTY_PASSWORD},
            render.context)
        self.assertEqual("jenkins", render.owner)
        self.assertEqual("nogroup", render.group)
