import os

from charmhelpers.core import hookenv
from charmhelpers.core import templating

from jenkinslib.paths import CONFIG_FILE

PORT = 8080


class Configuration(object):
    """Manage global Jenkins configuration."""

    # Legacy flag file used by former versions of this charm
    _legacy_bootstrap_flag = "/var/lib/jenkins/config.bootstrapped"

    def __init__(self, hookenv=hookenv, templating=templating):
        """
        @param hookenv: An object implementing the charmhelpers.core.hookenv
            API from charmhelpers (for testing).
        @param templating: An object implementing the
            charmhelpers.core.templating API from charmhelpers (for testing).
        """
        self._hookenv = hookenv
        self._templating = templating

    def bootstrap(self):
        """Generate Jenkins' config, if it hasn't done yet."""
        config = self._hookenv.config()

        # Only run on first invocation otherwise we blast
        # any configuration changes made
        if config.get("_config-bootstrapped"):
            self._hookenv.log("Jenkins was already configured, skipping")
            return

        self._hookenv.log("Bootstrapping initial Jenkins configuration")
        context = {"master_executors": config["master-executors"]}
        self._templating.render(
            "jenkins-config.xml", CONFIG_FILE, context,
            owner="jenkins", group="nogroup")

        config["_config-bootstrapped"] = True

        self._hookenv.open_port(PORT)

    def migrate(self):
        """Migrate the boostrap flag from the legacy file to local state."""
        config = self._hookenv.config()
        if os.path.exists(self._legacy_bootstrap_flag):
            config["_config-bootstrapped"] = True
            os.unlink(self._legacy_bootstrap_flag)
