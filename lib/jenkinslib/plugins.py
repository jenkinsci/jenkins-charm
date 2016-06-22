import os
import glob
import subprocess

from charmhelpers.core import hookenv
from charmhelpers.core import host

from jenkinslib.paths import PLUGINS


class Plugins(object):
    """Manage Jenkins plugins."""

    def __init__(self, subprocess=subprocess, hookenv=hookenv, host=host,
                 plugins_dir=PLUGINS):
        """
        @param subprocess: An object implementing the subprocess API (for
            testing).
        @param hookenv: An object implementing the charmhelpers.core.hookenv
            API from charmhelpers (for testing).
        @param host: An object implementing the charmhelpers.fetcher.archiveurl
            API from charmhelpers (for testing).
        @param plugins_dir: Path to Jenkins' plugins dir (for testing).
        """
        self._subprocess = subprocess
        self._hookenv = hookenv
        self._host = host
        self._plugins_dir = plugins_dir

    def install_configured_plugins(self):
        """Install all plugins requested via the charm config option."""
        self._hookenv.log("Stopping jenkins for plugin update(s)")
        self._host.service_stop("jenkins")
        plugins = self._hookenv.config()["plugins"].split()
        self.install_plugins(plugins)
        self._hookenv.log("Starting jenkins to pickup configuration changes")
        self._host.service_start("jenkins")

    def install_plugins(self, plugins):
        """Install the given plugins, optionally removing unlisted ones."""
        self._hookenv.log("Installing plugins (%s)" % " ".join(plugins))

        self._host.mkdir(
            self._plugins_dir, owner="jenkins", group="jenkins", perms=0o0755)

        existing_plugins = set(glob.glob("%s/*.hpi" % self._plugins_dir))

        config = self._hookenv.config()
        plugins_site = config["plugins-site"]

        self._hookenv.log("Fetching plugins from %s" % plugins_site)

        # NOTE: by default wget verifies certificates as of 1.10.
        if config["plugins-check-certificate"] == "no":
            wget_options = ("--no-check-certificate",)
        else:
            wget_options = ()

        installed_plugins = set()
        for plugin in plugins:
            path = self._install_plugin(plugins_site, plugin, wget_options)
            installed_plugins.add(path)

        unlisted_plugins = existing_plugins - installed_plugins
        if unlisted_plugins:
            if config["remove-unlisted-plugins"] == "yes":
                for plugin_path in unlisted_plugins:
                    if not os.path.isfile(plugin_path):
                        continue
                    self._hookenv.log("Deleting unlisted plugin '%s'" % path)
                    os.remove(plugin_path)
            else:
                self._hookenv.log(
                    "Unlisted plugins: (%s) Not removed. Set "
                    "remove-unlisted-plugins to 'yes' to clear them "
                    "away." % ", ".join(unlisted_plugins))

    def _install_plugin(self, plugins_site, plugin, wget_options):
        """Download and install a given plugin."""
        plugin_filename = "%s.hpi" % plugin
        url = os.path.join(plugins_site, plugin_filename)
        plugin_path = os.path.join(self._plugins_dir, plugin_filename)
        if not os.path.isfile(plugin_path):
            self._hookenv.log("Installing plugin %s" % plugin_filename)
            command = ("wget",) + wget_options + ("-q", "-O", "-", url)
            plugin_data = self._subprocess.check_output(command)
            self._host.write_file(
                plugin_path, plugin_data, owner="jenkins",
                group="jenkins", perms=0o0744)
        else:
            self._hookenv.log("Plugin %s already installed" % plugin_filename)
        return plugin_path
