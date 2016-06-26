import os

from charmhelpers.core import hookenv
from charmhelpers.core import host

from charms.layer.jenkins.paths import (
    HOME,
)

TOKEN_FILE = os.path.join(HOME, ".admin_token")


class Credentials(object):
    """Credentials for accessing the Jenkins master."""

    def __init__(self, hookenv=hookenv, host=host):
        """
        @param hookenv: An object implementing the charmhelpers.core.hookenv
            API from charmhelpers (for testing).
        @param host: An object implementing the charmhelpers.fetcher.archiveurl
            API from charmhelpers (for testing).
        """
        self._hookenv = hookenv
        self._host = host

    def username(self):
        """Get the username of the admin user, as set in the config."""
        return self._hookenv.config()["username"]

    def password(self):
        """Get the admin password from the config or from the local state."""
        password = self._hookenv.config()["password"]
        if not password:
            password = self._hookenv.config()["_generated-password"]
        return password

    def token(self, value=None):
        """Get or set the admin token from/to the local state."""
        config = self._hookenv.config()
        if value is not None:
            config["_api-token"] = value
            # Save the token to a file as well. It's not used directly by
            # this charm but it's convenient for integration with
            # third-party tools.
            self._host.write_file(
                TOKEN_FILE, value.encode("utf-8"), owner="root",
                group="root", perms=0o0600)
        return config.get("_api-token")
