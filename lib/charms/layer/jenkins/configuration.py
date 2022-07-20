import os
from urllib.parse import urlparse

from charmhelpers.core import hookenv
from charmhelpers.core import host
from charmhelpers.core import templating

from charms.layer.jenkins import paths
from charms.layer.jenkins.api import Api

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

    def configure_proxy(self):
        """Configure http(s) proxy settings if appropriate."""

        config = hookenv.config()

        api = Api()
        api.configure_proxy(
            config["proxy-hostname"],
            config["proxy-port"],
            config["proxy-username"],
            config["proxy-password"]
        )

    def migrate(self):
        """Drop the legacy boostrap flag file."""
        if os.path.exists(paths.LEGACY_BOOTSTRAP_FLAG):
            hookenv.log("Removing legacy bootstrap flag file")
            os.unlink(paths.LEGACY_BOOTSTRAP_FLAG)

    def set_url(self):
        """Update Jenkins public_url and prefix."""
        config = hookenv.config()
        url = config["public-url"]
        context = {"public_url": url}
        templating.render(
            "location-config.xml", paths.LOCATION_CONFIG_FILE, context,
            owner="jenkins", group="nogroup")

        self._set_prefix(urlparse(url).path)

    def _set_prefix(self, prefix):
        """ Set Jenkins to use the given prefix.
        :param prefix: The prefix Jenkins will be configured to use. If empty
                       the prefix config is unset.
        """
        # Since version 2.332.1 Jenkins is not loading env vars from the default config file
        overrides_content = '# This file is managed by Juju. Do not edit manually.\n[Service]\nEnvironment="JENKINS_PREFIX={}"\n'.format(prefix)

        host.mkdir(os.path.dirname(paths.SERVICE_CONFIG_FILE_OVERRIDE), perms=0o751)
        with open(os.open(paths.SERVICE_CONFIG_FILE_OVERRIDE, os.O_CREAT | os.O_WRONLY, 0o644), 'w') as overrides_file:
            overrides_file.write(overrides_content)

    def set_update_center_ca(self):
        """Configure Jenkins Update Center CA cert"""
        config = hookenv.config()
        ca_cert = config["update-center-ca"]
        ca_cert_file = os.path.join(paths.UPDATE_CENTER_ROOT_CAS,
                                    "default.crt")
        host.mkdir(paths.UPDATE_CENTER_ROOT_CAS, owner="jenkins", group="jenkins", perms=0o750)
        host.write_file(ca_cert_file, ca_cert, owner="jenkins", group="jenkins", perms=0o644)
