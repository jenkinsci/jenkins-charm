import os
import glob
import subprocess

from charmhelpers.core import hookenv, host

from charms.layer.jenkins import paths


class Plugins(object):
    """Manage Jenkins plugins."""

    def __init__(self, subprocess=subprocess):
        """
        @param subprocess: An object implementing the subprocess API (for
            testing).
        @param hookenv: An object implementing the charmhelpers.core.hookenv
            API from charmhelpers (for testing).
        """
        self._subprocess = subprocess

    def install(self, plugins):
        """Install the given plugins, optionally removing unlisted ones.

        @params plugins: A whitespace-separated list of plugins to install.
        """
        plugins = plugins or ""
        plugins = plugins.split()
        hookenv.log("Stopping jenkins for plugin update(s)")
        host.service_stop("jenkins")

        hookenv.log("Installing plugins (%s)" % " ".join(plugins))

        host.mkdir(
            paths.plugins(), owner="jenkins", group="jenkins", perms=0o0755)

        existing_plugins = set(glob.glob("%s/*.hpi" % paths.plugins()))
        installed_plugins = self._install_plugins(plugins)
        unlisted_plugins = existing_plugins - installed_plugins
        if unlisted_plugins:
            if hookenv.config()["remove-unlisted-plugins"] == "yes":
                self._remove_plugins(unlisted_plugins)
            else:
                hookenv.log(
                    "Unlisted plugins: (%s) Not removed. Set "
                    "remove-unlisted-plugins to 'yes' to clear them "
                    "away." % ", ".join(unlisted_plugins))

        hookenv.log("Starting jenkins to pickup configuration changes")
        host.service_start("jenkins")

    def _install_plugins(self, plugins):
        """Install the plugins with the given names."""
        config = hookenv.config()
        plugins_site = config["plugins-site"]

        hookenv.log("Fetching plugins from %s" % plugins_site)

        # NOTE: by default wget verifies certificates as of 1.10.
        if config["plugins-check-certificate"] == "no":
            wget_options = ("--no-check-certificate",)
        else:
            wget_options = ()
        paths = set()
        for plugin in plugins:
            path = self._install_plugin(plugins_site, plugin, wget_options)
            paths.add(path)
        return paths

    def _install_plugin(self, plugins_site, plugin, wget_options):
        """Download and install a given plugin."""
        plugin_filename = "%s.hpi" % plugin
        url = os.path.join(plugins_site, plugin_filename)
        plugin_path = os.path.join(paths.plugins(), plugin_filename)
        if not os.path.isfile(plugin_path):
            hookenv.log("Installing plugin %s" % plugin_filename)
            command = ("wget",) + wget_options + ("-q", "-O", "-", url)
            plugin_data = self._subprocess.check_output(command)
            host.write_file(
                plugin_path, plugin_data, owner="jenkins", group="jenkins",
                perms=0o0744)
        else:
            hookenv.log("Plugin %s already installed" % plugin_filename)
        return plugin_path

    def _remove_plugins(self, paths):
        """Remove the plugins at the given paths."""
        for path in paths:
            self._remove_plugin(path)

    def _remove_plugin(self, path):
        """Remove the plugin at the given path."""
        if not os.path.isfile(path):
            return
        hookenv.log("Deleting unlisted plugin '%s'" % path)
        os.remove(path)
