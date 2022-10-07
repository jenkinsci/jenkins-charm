import os

from collections import namedtuple

from charmhelpers.core import hookenv
from charmhelpers.core import host

from charms.layer.jenkins import paths
from charms.layer.jenkins.api import Api
from charms.layer.jenkins.packages import Packages


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
            paths.ADMIN_PASSWORD,
            admin.password.encode("utf-8"),
            owner="root",
            group="root",
            perms=0o0600,
        )

        if not os.path.exists(paths.LAST_EXEC):
            # This mean it's the very first time we configure the user,
            # and we want to create this file in order to avoid Jenkins
            # presenting the setup wizard.
            host.write_file(
                paths.LAST_EXEC,
                "{}\n".format(api.version()).encode("utf-8"),
                owner="jenkins",
                group="nogroup",
                perms=0o0600,
            )

    def _admin_data(self):
        """Get a named tuple holding configuration data for the admin user."""
        config = hookenv.config()
        username = config["username"]
        password = config["password"]

        if not password:
            password = host.pwgen(length=15)

        return _User(username, password)


_User = namedtuple("_User", ["username", "password"])
