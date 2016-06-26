import os
import hashlib

from collections import namedtuple

from charmhelpers.core import hookenv
from charmhelpers.core import host
from charmhelpers.core import templating
from charmhelpers.core.hookenv import DEBUG

from charms.layer.jenkins.paths import (
    USERS,
    HOME,
)

PASSWORD_FILE = os.path.join(HOME, ".admin_password")


class Users(object):
    """Manage Jenkins users."""

    def __init__(self, hookenv=hookenv, host=host, templating=templating):
        """
        @param hookenv: An object implementing the charmhelpers.core.hookenv
            API from charmhelpers (for testing).
        @param host: An object implementing the charmhelpers.fetcher.archiveurl
            API from charmhelpers (for testing).
        @param templating: An object implementing the
            charmhelpers.core.templating API from charmhelpers (for testing).
        """
        self._hookenv = hookenv
        self._host = host
        self._templating = templating

    def configure_admin(self):
        """Configure the admin user."""
        self._hookenv.log("Configuring user for jenkins.", level=DEBUG)

        admin = self._admin_data()

        # Save the password to a file. It's not used directly by this charm
        # but it's convenient for integration with third-party tools.
        self._host.write_file(
            PASSWORD_FILE, admin.password.encode("utf-8"), owner="root",
            group="root", perms=0o0600)

        admin_home = os.path.join(USERS, admin.username)
        self._host.mkdir(USERS, owner="jenkins", group="nogroup")
        self._host.mkdir(admin_home, owner="jenkins", group="nogroup")

        # NOTE: overwriting will destroy any data added by jenkins or the user.
        admin_config = os.path.join(admin_home, 'config.xml')
        context = {
            "username": admin.username, "password": admin.salty_password}
        self._templating.render(
            "user-config.xml", admin_config, context, owner="jenkins",
            group="nogroup")

    def _admin_data(self):
        """Get a named tuple holding configuration data for the admin user."""
        config = self._hookenv.config()
        username = config["username"]
        password = config["password"]

        if not password:
            password = self._host.pwgen(length=15)
            # Save the password to the local state, so it can be accessed
            # by the Credentials class.
            config["_generated-password"] = password

        # Generate Salt and Hash Password for Jenkins
        salt = self._host.pwgen(length=6)
        sha = hashlib.sha256(("%s{%s}" % (password, salt)).encode("utf-8"))
        salty_password = "%s:%s" % (salt, sha.hexdigest())

        return _User(username, password, salty_password)


_User = namedtuple("User", ["username", "password", "salty_password"])
