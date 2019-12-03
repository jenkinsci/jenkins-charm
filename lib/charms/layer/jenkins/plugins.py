import os
import pwd
import grp
import glob
import subprocess
import time
import urllib

from jenkins_plugin_manager.plugin import UpdateCenter

from charmhelpers.core import hookenv, host, unitdata

from charms.layer.jenkins import paths
from charms.layer.jenkins.api import Api


class Plugins(object):
    """Manage Jenkins plugins."""

    def install(self, plugins):
        """Install the given plugins, optionally removing unlisted ones.

        @params plugins: A whitespace-separated list of plugins to install.
        """
        hookenv.log("Starting plugins installation process")
        plugins = plugins or ""
        plugins = plugins.split()
        plugins = (self._get_plugins_to_install(plugins))

        host.mkdir(
            paths.PLUGINS, owner="jenkins", group="jenkins", perms=0o0755)
        existing_plugins = set(glob.glob("%s/*.jpi" % paths.PLUGINS))
        try:
            installed_plugins = self._install_plugins(plugins)
        except:
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
        self._restart_jenkins()

    def _install_plugins(self, plugins):
        """Install the plugins with the given names."""
        hookenv.log("Installing plugins (%s)" % " ".join(plugins))
        config = hookenv.config()
        plugins_site = config["plugins-site"]
        plugin_extension = config["plugins-site-extension"] or None
        plugin_paths = set()
        for plugin in plugins:
            plugin_path = self._install_plugin(
                plugin, plugins_site, plugin_extension)
            plugin_paths.add(plugin_path)
        return plugin_paths

    def _install_plugin(self, plugin, plugins_site, plugin_extension):
        # TODO verify if plugin is available and in the latest version before
        #      installing it
        plugin_url = (
                "%s/%s.%s" % (plugins_site, plugin, plugin_extension))
        return self._download_plugin(plugin, plugin_url)

    # Keeping the funcionality while the new _install_plugins()
    # doens't verify for installed plugins
    def _install_plugins_old(self, plugins):
        """Install the plugins with the given names."""
        config = hookenv.config()
        plugins_site = config["plugins-site"]

        hookenv.log("Fetching plugins from %s" % plugins_site)

        # NOTE: by default wget verifies certificates as of 1.10.
        if config["plugins-check-certificate"] == "no":
            wget_options = ["--no-check-certificate"]
        else:
            wget_options = []
        update = config["plugins-force-reinstall"] or config["plugins-auto-update"]
        if update:
            wget_options.append("-N")
        paths = set()
        for plugin in plugins:
            path = self._install_plugin_old(plugins_site, plugin, wget_options, update)
            paths.add(path)
        return paths

    # Keeping the funcionality while the new _install_plugins()
    # doens't verify for installed plugins
    def _install_plugin_old(self, plugins_site, plugin, wget_options, update):
        """Download and install a given plugin."""
        plugin_filename = "%s.hpi" % plugin
        url = os.path.join(plugins_site, plugin_filename)
        plugin_path = os.path.join(paths.PLUGINS, plugin_filename)
        if not os.path.isfile(plugin_path) or update:
            # Get when was the last time this plugin was updated
            if os.path.isfile(plugin_path):
                last_update = os.path.getmtime(plugin_path)
            else:
                last_update = 0
            hookenv.log("Installing plugin %s" % plugin_filename)
            command = ["wget"] + wget_options + ["-q", url]
            subprocess.check_output(command, cwd=paths.PLUGINS)
            if os.path.getmtime(plugin_path) != last_update:
                uid = pwd.getpwnam('jenkins').pw_uid
                gid = grp.getgrnam('jenkins').gr_gid
                os.chown(plugin_path, uid, gid)
                os.chmod(plugin_path, 0o0744)
                hookenv.log("A new version of %s has been installed" % plugin_filename)
                unitdata.kv().set('jenkins.plugins.last_plugin_update_time', time.time())

            else:
                hookenv.log("Plugin %s is already in latest version"
                            % plugin_filename)

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

    def _get_plugins_to_install(self, plugins, uc=None):
        """Get all plugins needed to be installed"""
        uc = uc or UpdateCenter()
        plugins_and_dependencies = uc.get_plugins(plugins)
        if plugins == plugins_and_dependencies:
            return plugins
        else:
            return self._get_plugins_to_install(plugins_and_dependencies, uc)

    def _download_plugin(self, plugin, plugin_site):
        """Get dependencies of the given plugin(s)"""
        uc = UpdateCenter()
        return uc.download_plugin(
                plugin, paths.PLUGINS, plugin_url=plugin_site)

    def update(self, plugins, path=None):
        """Try to update the given plugins.

        @params plugins: A whitespace-separated list of plugins to install.
        """
        plugins = plugins or ""
        plugins = plugins.split()
        hookenv.log("Updating plugins")
        try:
            # Keeping the funcionality while the new _install_plugins()
            # doens't verify for installed plugins
            self._install_plugins_old(plugins)
        except Exception:
            hookenv.log("Plugin installation failed, check logs for details")
            raise

    def _restart_jenkins(self):
        api = Api()
        api.restart()
        api.wait()  # Wait for the service to be fully up
        unitdata.kv().set("jenkins.last_restart", time.time())
