import os

from charmtest import CharmTest

from charmhelpers.core import hookenv

from charms.layer.jenkins import paths
from charms.layer.jenkins.users import Users


class UsersTest(CharmTest):

    def setUp(self):
        super(UsersTest, self).setUp()
        self.filesystem.add(paths.HOME)
        self.users.add("jenkins", 123)
        self.groups.add("nogroup", 456)

        self.templates_dir = os.path.join(hookenv.charm_dir(), "templates")
        root_dir = os.path.dirname(os.path.dirname(__file__))
        os.symlink(os.path.join(root_dir, "templates"), self.templates_dir)

        self.users = Users()

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
        self.assertTrue(hookenv.config()["_generated-password"])

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

        path = os.path.join(paths.users(), "admin", "config.xml")
        with open(path) as fd:
            content = fd.read()
        self.assertIn("<fullName>admin</fullName>", content)
        self.assertEqual(123, self.filesystem.uid[path])
        self.assertEqual(456, self.filesystem.gid[path])
