from charmhelpers.core import hookenv


class Credentials(object):
    """Credentials for accessing the Jenkins master."""

    def __init__(self, hookenv=hookenv):
        """
        @param hookenv: An object implementing the charmhelpers.core.hookenv
            API from charmhelpers (for testing).
        """
        self._hookenv = hookenv

    def username(self):
        """Get the username of the admin user, as set in the config."""
        return self._hookenv.config()["username"]

    def password(self):
        """Get the admin password from the config or from the local state."""
        password = self._hookenv.config()["password"]
        if not password:
            password = self._hookenv.config()["_generated-password"]
        return password
