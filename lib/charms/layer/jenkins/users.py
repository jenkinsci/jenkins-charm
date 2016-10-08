import os
import hashlib

from collections import namedtuple

from charmhelpers.core import hookenv
from charmhelpers.core import host
from charmhelpers.core import templating
from charmhelpers.core.hookenv import DEBUG

from charms.layer.jenkins import paths


class Users(object):
    """Manage Jenkins users."""

    def configure_admin(self):
        """Configure the admin user."""
        hookenv.log("Configuring user for jenkins.", level=DEBUG)

        admin = self._admin_data()

        # Save the password to a file. It's not used directly by this charm
        # but it's convenient for integration with third-party tools.
        host.write_file(
            paths.ADMIN_PASSWORD, admin.password.encode("utf-8"),
            owner="root", group="root", perms=0o0600)

        admin_home = os.path.join(paths.USERS, admin.username)
        self._make_jenkins_dir(paths.USERS)
        self._make_jenkins_dir(admin_home)

        # NOTE: overwriting will destroy any data added by jenkins or the user.
        admin_config = os.path.join(admin_home, "config.xml")
        context = {
            "username": admin.username, "password": admin.salty_password}
        templating.render(
            "user-config.xml", admin_config, context, owner="jenkins",
            group="nogroup")

    def _admin_data(self):
        """Get a named tuple holding configuration data for the admin user."""
        config = hookenv.config()
        username = config["username"]
        password = config["password"]

        if not password:
            password = host.pwgen(length=15)
            # Save the password to the local state, so it can be accessed
            # by the Credentials class.
            config["_generated-password"] = password

        return _User(username, password, _salty_password(password))

    def _make_jenkins_dir(self, path):
        """Create a directory under Jenkins' home."""
        host.mkdir(path, owner="jenkins", group="nogroup", perms=0o0700)


def _salty_password(password):
    """Generate Salt and Hash Password for Jenkins."""
    salt = host.pwgen(length=6)
    sha = hashlib.sha256(("%s{%s}" % (password, salt)).encode("utf-8"))
    return "%s:%s" % (salt, sha.hexdigest())


_User = namedtuple("User", ["username", "password", "salty_password"])
