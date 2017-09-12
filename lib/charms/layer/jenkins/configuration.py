import os
from urllib.parse import urlparse

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

        if not -1 <= config["jnlp-port"] <= 65535:
            err = "{} is not a valid setting for jnlp-port".format(
                config["jnlp-port"]
            )
            hookenv.log(err)
            hookenv.status_set("blocked", err)
            return False
        else:
            context = {
                "master_executors": config["master-executors"],
                "jnlp_port": config["jnlp-port"]}

            templating.render(
                "jenkins-config.xml", paths.CONFIG_FILE, context,
                owner="jenkins", group="nogroup")

            hookenv.open_port(PORT)

            # if we're using a set JNLP port, open it
            if config["jnlp-port"] > 0:
                hookenv.open_port(config["jnlp-port"])

            return True

    def migrate(self):
        """Drop the legacy boostrap flag file."""
        if os.path.exists(paths.LEGACY_BOOTSTRAP_FLAG):
            hookenv.log("Removing legacy bootstrap flag file")
            os.unlink(paths.LEGACY_BOOTSTRAP_FLAG)

    def set_url(self):
        """Update Jenkins public_url and prefix
            return True when a restart is required, false and a
            reload via the API is sufficient.
        """
        config = hookenv.config()
        url = config["public-url"]
        context = {"public_url": url}
        templating.render(
            "location-config.xml", paths.LOCATION_CONFIG_FILE, context,
            owner="jenkins", group="nogroup")

        return self._set_prefix(urlparse(url).path)

    def _set_prefix(self, prefix):
        """ Set Jenkins to use the given prefix.
        :param prefix: The prefix Jenkins will be configured to use. If empty
                       the prefix config is unset.
        :return: True when an update was made, false otherwise.
        """
        if not os.path.exists(paths.DEFAULTS_CONFIG_FILE):
            hookenv.log("Defaults file {} not found, Jenkins prefix not set.".
                        format(paths.DEFAULTS_CONFIG_FILE))
            return False

        prefix_line_base = 'JENKINS_ARGS="$JENKINS_ARGS --prefix='
        prefix_line = prefix_line_base + prefix + '"'
        defaults_content = ""

        update = False
        found = False
        with open(paths.DEFAULTS_CONFIG_FILE, 'r') as defaults:
            for line in defaults:
                if line.startswith(prefix_line_base):
                    found = True
                    if not line.startswith(prefix_line):
                        update = True
                    continue
                defaults_content += line

        if prefix:
            defaults_content += "\n" + prefix_line
            if not found:
                update = True

        if update:
            with open(paths.DEFAULTS_CONFIG_FILE, 'w') as defaults_file:
                defaults_file.write(defaults_content + "\n")
            return True

        return False
