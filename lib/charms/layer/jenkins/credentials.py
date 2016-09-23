from charmhelpers.core import hookenv
from charmhelpers.core import host

from charms.layer.jenkins import paths


class Credentials(object):
    """Credentials for accessing the Jenkins master."""

    def username(self):
        """Get the username of the admin user, as set in the config."""
        return hookenv.config()["username"]

    def password(self):
        """Get the admin password from the config or from the local state."""
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
                paths.admin_token(), value.encode("utf-8"), owner="root",
                group="root", perms=0o0600)
        return config.get("_api-token")
