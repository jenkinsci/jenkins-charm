import os

from charmtest import CharmTest

from charmhelpers.core import hookenv

from stubs.host import HostStub
from stubs.templating import TemplatingStub

from charms.layer.jenkins import paths
from charms.layer.jenkins.users import Users

# SHA256 version of the hard-coded random password from HostStub.password
SALTY_PASSWORD = (
    "eegh5a:3c5eb427399cab549de5139adb70644a7c5580657f6b01f2b2f3380f0f2ce9b7")


class UsersTest(CharmTest):

    def setUp(self):
        super(UsersTest, self).setUp()
        self.host = HostStub()
        self.templating = TemplatingStub()
        self.filesystem.add(paths.HOME)
        self.users.add("jenkins", 123)
        self.groups.add("nogroup", 456)

        self.users = Users(host=self.host, templating=self.templating)

    def test_configure_admin_custom_password(self):
        """
        If a password is provided, it's used to configure the admin user.
        """
        self.application.config.update({
            "master-executors": 1,
            "username": "admin",
            "password": "sekret",
        })
        self.users.configure_admin()
        with open(paths.admin_password()) as fd:
            self.assertEqual("sekret", fd.read())
        self.assertEqual(0, self.filesystem.uid[paths.admin_password()])
        self.assertEqual(0, self.filesystem.gid[paths.admin_password()])
        self.assertEqual(0o100600, os.stat(paths.admin_password()).st_mode)

    def test_configure_admin_random_password(self):
        """
        If a password is not provided, a random one will be generated.
        """
        self.application.config.update({
            "username": "admin",
            "password": ""})
        self.users.configure_admin()
        self.assertEqual(
            self.host.password, hookenv.config()["_generated-password"])

    def test_configure_admin_make_users_dir(self):
        """
        The Jenkins user directories are created with proper permissions.
        """
        self.application.config.update({
            "username": "admin",
            "password": ""})
        self.users.configure_admin()

        self.assertTrue(os.path.exists(paths.users()))
        self.assertEqual(123, self.filesystem.uid[paths.users()])
        self.assertEqual(456, self.filesystem.gid[paths.users()])

        admin_user_dir = os.path.join(paths.users(), "admin")
        self.assertTrue(os.path.exists(admin_user_dir))
        self.assertEqual(123, self.filesystem.uid[admin_user_dir])
        self.assertEqual(456, self.filesystem.gid[admin_user_dir])
        self.assertEqual(0o40700, os.stat(admin_user_dir).st_mode)

    def test_configure_admin_write_user_config(self):
        """
        A Jenkins user-config.xml file is written with the appropriate
        details.
        """
        self.application.config.update({
            "username": "admin",
            "password": ""})
        self.users.configure_admin()
        render = self.templating.renders[0]
        self.assertEqual("user-config.xml", render.source)
        self.assertEqual(
            os.path.join(paths.users(), "admin", "config.xml"),
            render.target)
        self.assertEqual(
            {"username": "admin", "password": SALTY_PASSWORD},
            render.context)
        self.assertEqual("jenkins", render.owner)
        self.assertEqual("nogroup", render.group)
