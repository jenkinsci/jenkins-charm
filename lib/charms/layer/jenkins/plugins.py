import os
import pwd
import grp
import glob
import subprocess
import time

from charmhelpers.core import hookenv, host

from charms.layer.jenkins import paths


class Plugins(object):
    """Manage Jenkins plugins."""

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
            paths.PLUGINS, owner="jenkins", group="jenkins", perms=0o0755)

        existing_plugins = set(glob.glob("%s/*.hpi" % paths.PLUGINS))
        try:
            installed_plugins = self._install_plugins(plugins)
        except:
            hookenv.log("Plugin installation failed, check logs for details")
            host.service_start("jenkins")  # Make sure we don't leave jenkins down
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
        if (config["plugins-force-reinstall"] == "no" and
                config["plugins-auto-update"] == "no"):
            update = False
        else:
            update = True
            wget_options = ("-N",) + wget_options
        paths = set()
        for plugin in plugins:
            path = self._install_plugin(plugins_site, plugin, wget_options, update)
            paths.add(path)
        return paths

    def _install_plugin(self, plugins_site, plugin, wget_options, update):
        """Download and install a given plugin."""
        plugin_filename = "%s.hpi" % plugin
        url = os.path.join(plugins_site, plugin_filename)
        plugin_path = os.path.join(paths.PLUGINS, plugin_filename)
        if not os.path.isfile(plugin_path) or update:
            hookenv.log("Installing plugin %s" % plugin_filename)
            command = ("wget",) + wget_options + ("-q", url)
            subprocess.check_output(command, cwd=paths.PLUGINS)
            uid = pwd.getpwnam('jenkins').pw_uid
            gid = grp.getgrnam('jenkins').gr_gid
            os.chown(plugin_path, uid, gid)
            os.chmod(plugin_path, 0o0744)
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

    def update(self, plugins, path=None):
        """Try to update the given plugins.

        @params plugins: A whitespace-separated list of plugins to install.
        """
        plugins = plugins or ""
        plugins = plugins.split()
        path = path or paths.PLUGINS
        last_update_file = os.path.join(path, "last_update.log")
        if not os.path.isfile(last_update_file):
            host.write_file(
                last_update_file, "", owner="jenkins", group="jenkins",
                perms=0o0744)
            os.utime(last_update_file, (0, 0))
        # Only try to update once every 30 min.
        last_update_time = os.path.getmtime(last_update_file)
        interval = (time.time() - (30 * 60))
        if (last_update_time < interval):
            hookenv.log("Updating plugins")
            try:
                self._install_plugins(plugins)
                now = time.time()
                os.utime(last_update_file, (now, now))
            except:
                hookenv.log("Plugin installation failed, check logs for details")
                raise
