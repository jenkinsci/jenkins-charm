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
            with open(paths.ADMIN_PASSWORD, 'r') as f:
                password = f.read().strip()
        return password

    def token(self, value=None):
        """Get or set the admin token from/to the local state."""
        if value is not None:
            # Save the token to a file
            host.write_file(
                paths.ADMIN_TOKEN, value.encode("utf-8"), owner="root",
                group="root", perms=0o0600)
        if not os.path.exists(paths.ADMIN_TOKEN):
            return None
        with open(paths.ADMIN_TOKEN, 'r') as f:
            return f.read().strip()

    def _initial_password(self):
        """Return the initial admin password."""
        with open(paths.INITIAL_PASSWORD) as fd:
            return fd.read().strip()

    def _user_configured(self):
        """Whether the first user has been configured yet."""
        return os.path.exists(paths.ADMIN_PASSWORD)
