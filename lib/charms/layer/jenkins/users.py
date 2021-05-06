import os

from collections import namedtuple

from charmhelpers.core import hookenv
from charmhelpers.core import host

from charms.layer.jenkins import paths
from charms.layer.jenkins.api import Api
from charms.layer.jenkins.packages import Packages


class AdminUserNotConfiguredException(Exception):
    """An exception to indicate the admin user hasn't been configured yet."""


class Users(object):
    """Manage Jenkins users."""

    def __init__(self, packages=None):
        self._packages = packages or Packages()

    def configure_admin(self):
        """Configure the admin user."""
        hookenv.log("Configuring user for jenkins")

        admin = self._admin_data()
        api = Api(packages=self._packages)
        api.update_password(admin.username, admin.password)

        # Save the password to a file. It's not used directly by this charm
        # but it's convenient for integration with third-party tools.
        host.write_file(
            paths.ADMIN_PASSWORD, admin.password.encode("utf-8"),
            owner="root", group="root", perms=0o0600)

        if not os.path.exists(paths.LAST_EXEC):
            # This mean it's the very first time we configure the user,
            # and we want to create this file in order to avoid Jenkins
            # presenting the setup wizard.
            host.write_file(
                paths.LAST_EXEC, "{}\n".format(api.version()).encode("utf-8"),
                owner="jenkins", group="nogroup", perms=0o0600)

    def get_admin_password(self):
        """Get our admin password."""
        # We don't want to create a password if it doesn't exist, because we'd
        # also need to update it in Jenkins via the API call, and write it to
        # a file. Instead we'll rely on `configure_admin` having been run.
        admin = self._admin_data(autogen_password_if_empty=False)
        return admin.password

    def _admin_data(self, autogen_password_if_empty=True):
        """Get a named tuple holding configuration data for the admin user.

        Takes an optional variable of `autogen_password_if_empty` to say
        whether to create a password if it doesn't exist. If we're calling
        this from a function that later persists that password to disk, we
        want to do so but if we're simply trying to read the password."""
        config = hookenv.config()
        username = config["username"]
        password = config["password"]

        if not password:
            if os.path.exists(paths.ADMIN_PASSWORD):
                with open(paths.ADMIN_PASSWORD, 'r') as admin_password_file:
                    password = admin_password_file.read()
            else:
                if autogen_password_if_empty:
                    password = host.pwgen(length=15)
                else:
                    raise AdminUserNotConfiguredException

        return _User(username, password)


_User = namedtuple("User", ["username", "password"])
