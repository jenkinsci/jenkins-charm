import glob
import os
import shutil
import urllib
from distutils.dir_util import copy_tree, remove_tree

from charmhelpers.core import hookenv, host
from charms.layer.jenkins import paths
from charms.layer.jenkins.api import Api

from jenkins_plugin_manager.plugin import UpdateCenter


class PluginSiteError(Exception):
    def __init__(self):
        self.message = ("The configured plugin-site doesn't provide an "
                        "update-center.json file or is not acessible.")


class Plugins(object):
    """Manage Jenkins plugins."""

    def __init__(self):
        if hookenv.config()["plugins-site"] == "https://updates.jenkins-ci.org/latest/":
            self.update_center = UpdateCenter()
        else:
            plugins_site = hookenv.config()["plugins-site"]
            try:
                update_center = plugins_site + "/update-center.json"
                urllib.request.urlopen(update_center)
                self.update_center = UpdateCenter(uc_url=update_center)
            except urllib.error.HTTPError:
                raise PluginSiteError()

    def install(self, plugins):
        """Install the given plugins, optionally removing unlisted ones.

        @params plugins: A whitespace-separated list of plugins to install.
        """
        hookenv.log("Starting plugins installation process")
        plugins = plugins or ""
        plugins = plugins.split()
        plugins, incompatible_plugins = self._get_plugins_to_install(plugins)
        if len(incompatible_plugins) != 0:
            hookenv.log("The following plugins require a higher jenkins version"
                        " and were not installed: (%s)" % " ".join(
                            incompatible_plugins))
        configured_plugins = self._get_plugins_to_install(
            hookenv.config()["plugins"].split())
        host.mkdir(
            paths.PLUGINS, owner="jenkins", group="jenkins", perms=0o0755)
        existing_plugins = set(glob.glob("%s/*.[h|j]pi" % paths.PLUGINS))
        try:
            self._install_plugins(plugins)
        except Exception:
            hookenv.log("Plugin installation failed, check logs for details")
            raise

        plugin_file_names = tuple(map(lambda x: "/{}.jpi".format(x), configured_plugins))
        installed_plugins = set(filter(lambda x: x.endswith(plugin_file_names), existing_plugins))
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
        return installed_plugins, incompatible_plugins

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
        # Make sure that the plugin directory is owned by jenkins
        host.chownr(paths.PLUGINS, owner="jenkins", group="jenkins", chowntopdir=True)
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
            # Plugins might be either .hpi or .jpi files.
            try:
                plugin_url = ("%s/%s.hpi" % (plugins_site, plugin))
                return self._download_plugin(plugin, plugin_url)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    plugin_url = ("%s/%s.jpi" % (plugins_site, plugin))
                    return self._download_plugin(plugin, plugin_url)
                else:
                    raise
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
            return self._exclude_incompatible_plugins(plugins)
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

    def _get_required_jenkins(self, plugin):
        """Get the jenkins version required for a plugin"""
        return self._get_plugin_info(plugin)["requiredCore"]

    def _exclude_incompatible_plugins(self, plugins):
        """Exclude plugins incompatible with the jenkins version"""
        excluded_plugins = []
        jenkins_version = Api().version()
        for plugin in plugins:
            required_version = self._get_required_jenkins(plugin)
            if not self.update_center._check_min_core_version(
                                    jenkins_version, required_version):
                excluded_plugins.append(plugin)
        plugins = [
            plugin for plugin in plugins if plugin not in excluded_plugins]

        return plugins, excluded_plugins

    def backup(self):
        """Backup plugins.
        """
        hookenv.log("Backing up plugins.")
        copy_tree(paths.PLUGINS, paths.PLUGINS_BACKUP)

    def restore(self):
        """Restore plugins from backup directory."""
        hookenv.log("Restoring plugins from backup.")
        remove_tree(paths.PLUGINS)
        copy_tree(paths.PLUGINS_BACKUP, paths.PLUGINS)
        shutil.chown(paths.PLUGINS, user="jenkins", group="jenkins")

    def clean_backup(self):
        """Remove backup directory."""
        hookenv.log("Cleaning up backup plugins.")
        remove_tree(paths.PLUGINS_BACKUP)
