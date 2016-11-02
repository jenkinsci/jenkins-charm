import os

from charmhelpers.core import hookenv
from charmhelpers.core import templating

from charms.layer.jenkins import paths

PORT = 8080


class Configuration(object):
    """Manage global Jenkins configuration."""

    def bootstrap(self):
        """Generate Jenkins' initial config."""
        hookenv.log("Bootstrapping initial Jenkins configuration")

        config = hookenv.config()
        context = {"master_executors": config["master-executors"]}
        templating.render(
            "jenkins-config.xml", paths.CONFIG_FILE, context,
            owner="jenkins", group="nogroup")

        hookenv.open_port(PORT)

    def migrate(self):
        """Drop the legacy boostrap flag file."""
        if os.path.exists(paths.LEGACY_BOOTSTRAP_FLAG):
            hookenv.log("Removing legacy bootstrap flag file")
            os.unlink(paths.LEGACY_BOOTSTRAP_FLAG)
