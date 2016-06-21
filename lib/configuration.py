from paths import CONFIG_FILE

from charmhelpers.core import hookenv
from charmhelpers.core import templating

PORT = 8080


class Configuration(object):
    """Manage global Jenkins configuration."""

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
            return

        self._hookenv.log(
            "Bootstrapping secure initial configuration in Jenkins.")
        context = {"master_executors": config["master-executors"]}
        self._templating.render(
            "jenkins-config.xml", CONFIG_FILE, context,
            owner="jenkins", group="nogroup")

        config["_config-bootstrapped"] = True

        self._hookenv.open_port(PORT)
