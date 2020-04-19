import glob
import os
import urllib

from charmhelpers.core import hookenv, host
from charms.layer.jenkins import paths
from charms.layer.jenkins.api import Api

from jenkins_plugin_manager.plugin import UpdateCenter


class Plugins(object):
    """Manage Jenkins plugins."""

    def __init__(self):
        plugins_site = hookenv.config()["plugins-site"]
        try:
            update_center = plugins_site + "/update-center.json"
            urllib.request.urlopen(update_center)
            self.update_center = UpdateCenter(uc_url=update_center)
        except urllib.error.HTTPError:
            self.update_center = UpdateCenter()

    def install(self, plugins):
        """Install the given plugins, optionally removing unlisted ones.

        @params plugins: A whitespace-separated list of plugins to install.
        """
        hookenv.log("Starting plugins installation process")
        plugins = plugins or ""
        plugins = plugins.split()
        plugins = self._get_plugins_to_install(plugins)

        host.mkdir(
            paths.PLUGINS, owner="jenkins", group="jenkins", perms=0o0755)
        existing_plugins = set(glob.glob("%s/*.jpi" % paths.PLUGINS))
        try:
            installed_plugins = self._install_plugins(plugins)
        except Exception:
            hookenv.log("Plugin installation failed, check logs for details")
            raise

        unlisted_plugins = existing_plugins - installed_plugins
        if unlisted_plugins:
            if hookenv.config()["remove-unlisted-plugins"] == "yes":
                self._remove_plugins(unlisted_plugins)
            else:
                hookenv.log(
                    "Unlisted plugins: (%s) Not removed. Set "
                    "remove-unlisted-plugins to 'yes' to clear them "
                    "away." % ", ".join(unlisted_plugins))

        # Restarting jenkins to pickup configuration changes
        Api().restart()
        return installed_plugins

    def _install_plugins(self, plugins):
        """Install the plugins with the given names."""
        hookenv.log("Installing plugins (%s)" % " ".join(plugins))
        config = hookenv.config()
        update = config["plugins-auto-update"]
        plugins_site = config["plugins-site"]
        plugin_paths = set()
        for plugin in plugins:
            plugin_path = self._install_plugin(
                plugin, plugins_site, update)
            if plugin_path is None:
                pass
            elif plugin_path:
                plugin_paths.add(plugin_path)
            else:
                hookenv.log("Failed to download %s" % plugin)
        return plugin_paths

    def _install_plugin(self, plugin, plugins_site, update):
        """
        Verify if the plugin is not installed before installing it
        or if it needs an update .
        """
        plugin_version = Api().get_plugin_version(plugin)
        latest_version = self._get_latest_version(plugin)
        if not plugin_version or (update and plugin_version != latest_version):
            hookenv.log("Installing plugin %s-%s" % (plugin, latest_version))
            plugin_url = (
                "%s/%s.hpi" % (plugins_site, plugin))
            return self._download_plugin(plugin, plugin_url)
        hookenv.log("Plugin %s-%s already installed" % (
            plugin, plugin_version))

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

    def _get_plugins_to_install(self, plugins, uc=None):
        """Get all plugins needed to be installed"""
        uc = uc or self.update_center
        plugins_and_dependencies = uc.get_plugins(plugins)
        if plugins == plugins_and_dependencies:
            return plugins
        else:
            return self._get_plugins_to_install(plugins_and_dependencies, uc)

    def _download_plugin(self, plugin, plugin_site):
        """Get dependencies of the given plugin(s)"""
        uc = self.update_center
        return uc.download_plugin(
                plugin, paths.PLUGINS, plugin_url=plugin_site,
                with_version=False)

    def _get_plugin_info(self, plugin):
        """Get info of the given plugin from the UpdateCenter"""
        uc = self.update_center
        return uc.get_plugin_data(plugin)

    def _get_latest_version(self, plugin):
        """Get the latest available version of a plugin"""
        return self._get_plugin_info(plugin)["version"]

    def update(self, plugins):
        """Try to update the given plugins.

        @params plugins: A whitespace-separated list of plugins to install.
        """
        plugins = plugins or ""
        plugins = plugins.split()
        plugins = self._get_plugins_to_install(plugins)
        hookenv.log("Updating plugins")
        try:
            installed_plugins = self._install_plugins(plugins)
        except Exception:
            hookenv.log("Plugin update failed, check logs for details")
            raise

        if len(installed_plugins) == 0:
            hookenv.log("No plugins updated")
            return
        else:
            Api().restart()
            return installed_plugins
