import os

from charmhelpers.core import hookenv
from charmhelpers.core import templating

from charms.layer.jenkins import paths

PORT = 8080


class Configuration(object):
    """Manage global Jenkins configuration."""

    # Legacy flag file used by former versions of this charm
    _legacy_bootstrap_flag = "/var/lib/jenkins/config.bootstrapped"

    def bootstrap(self):
        """Generate Jenkins' config, if it hasn't done yet."""
        config = hookenv.config()

        # Only run on first invocation otherwise we blast
        # any configuration changes made
        if config.get("_config-bootstrapped"):
            hookenv.log("Jenkins was already configured, skipping")
            return

        hookenv.log("Bootstrapping initial Jenkins configuration")
        context = {"master_executors": config["master-executors"]}
        templating.render(
            "jenkins-config.xml", paths.config_file(), context,
            owner="jenkins", group="nogroup")

        config["_config-bootstrapped"] = True

        hookenv.open_port(PORT)

    def migrate(self):
        """Migrate the boostrap flag from the legacy file to local state."""
        config = hookenv.config()
        if os.path.exists(self._legacy_bootstrap_flag):
            config["_config-bootstrapped"] = True
            os.unlink(self._legacy_bootstrap_flag)
