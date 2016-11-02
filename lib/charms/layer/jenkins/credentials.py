import os

from charmhelpers.core import hookenv
from charmhelpers.core import host

from charms.layer.jenkins import paths

INITIAL_USERNAME = "admin"


class Credentials(object):
    """Credentials for accessing the Jenkins master."""

    def username(self):
        """Get the username to use (either the initial or configured one)."""
        if not self._user_configured():
            # If we haven't configured the first user yet, let's use the
            # initial admin username.
            return INITIAL_USERNAME
        return hookenv.config()["username"]

    def password(self):
        """Get the admin password from the config or from the local state."""
        if not self._user_configured():
            # If we haven't configured the first user yet, let's use the
            # initial admin password.
            return self._initial_password()

        password = hookenv.config()["password"]
        if not password:
            password = hookenv.config()["_generated-password"]
        return password

    def token(self, value=None):
        """Get or set the admin token from/to the local state."""
        config = hookenv.config()
        if value is not None:
            config["_api-token"] = value
            # Save the token to a file as well. It's not used directly by
            # this charm but it's convenient for integration with
            # third-party tools.
            host.write_file(
                paths.ADMIN_TOKEN, value.encode("utf-8"), owner="root",
                group="root", perms=0o0600)
        return config.get("_api-token")

    def _initial_password(self):
        """Return the initial admin password."""
        with open(paths.INITIAL_PASSWORD) as fd:
            return fd.read().strip()

    def _user_configured(self):
        """Whether the first user has been configured yet."""
        return os.path.exists(paths.ADMIN_PASSWORD)
