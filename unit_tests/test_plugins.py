import os

from testtools.matchers import (
    PathExists,
    FileContains,
    Not,
)

from charmhelpers.core import hookenv

from charmtest import CharmTest

from charms.layer.jenkins import paths
from charms.layer.jenkins.plugins import Plugins


class PluginsTest(CharmTest):

    def setUp(self):
        super(PluginsTest, self).setUp()
        self.plugins = Plugins()

        self.fakes.fs.add(paths.PLUGINS)
        os.makedirs(paths.PLUGINS)
        self.fakes.users.add("jenkins", 123)
        self.fakes.groups.add("jenkins", 123)
        self.orig_plugins_site = hookenv.config()["plugins-site"]
        hookenv.config()["plugins-site"] = "http://x/"
        self.fakes.processes.wget.locations["http://x/plugin.hpi"] = b"data"

    def tearDown(self):
        super(PluginsTest, self).tearDown()
        hookenv.config()["plugins-site"] = self.orig_plugins_site

    def test_install(self):
        """
        The given plugins are downloaded from the Jenkins site.
        """
        self.plugins.install("plugin")
        self.assertEqual(
            ["stop", "start"],
            self.fakes.processes.systemctl.actions["jenkins"])
        plugin_path = os.path.join(paths.PLUGINS, "plugin.hpi")
        self.assertThat(plugin_path, FileContains("data"))

    def test_install_no_certificate_check(self):
        """
        If plugins-check-certificate is set to 'no', the plugins site
        certificate won't be validated.
        """
        orig_plugins_check_certificate = hookenv.config()["plugins-check-certificate"]
        try:
            hookenv.config()["plugins-check-certificate"] = "no"
            self.plugins.install("plugin")
            self.assertIn(
                "--no-check-certificate", self.fakes.processes.procs[-4].args)
        finally:
            hookenv.config()["plugins-check-certificate"] = orig_plugins_check_certificate

    def test_install_dont_remove_unlisted(self):
        """
        If remove-unlisted-plugins is set to 'yes', then unlisted plugins
        are removed from disk.
        """
        orig_remove_unlisted_plugins = hookenv.config()["remove-unlisted-plugins"]
        try:
            hookenv.config()["remove-unlisted-plugins"] = "yes"
            unlisted_plugin = os.path.join(paths.PLUGINS, "unlisted.hpi")
            with open(unlisted_plugin, "w"):
                pass
            self.plugins.install("plugin")
            self.assertThat(unlisted_plugin, Not(PathExists()))
        finally:
            hookenv.config()["remove-unlisted-plugins"] = orig_remove_unlisted_plugins

    def test_install_do_remove_unlisted(self):
        """
        If remove-unlisted-plugins is set to 'no', then unlisted plugins
        will be left on disk.
        """
        unlisted_plugin = os.path.join(paths.PLUGINS, "unlisted.hpi")
        with open(unlisted_plugin, "w"):
            pass
        self.plugins.install("plugin")
        self.assertThat(unlisted_plugin, PathExists())

    def test_install_skip_non_file_unlisted(self):
        """
        If an unlisted plugin is not actually a file, it's just skipped and
        doesn't get removed.
        """
        orig_remove_unlisted_plugins = hookenv.config()["remove-unlisted-plugins"]
        try:
            hookenv.config()["remove-unlisted-plugins"] = "yes"
            unlisted_plugin = os.path.join(paths.PLUGINS, "unlisted.hpi")
            os.mkdir(unlisted_plugin)
            self.plugins.install("plugin")
            self.assertThat(unlisted_plugin, PathExists())
        finally:
            hookenv.config()["remove-unlisted-plugins"] = orig_remove_unlisted_plugins

    def test_install_already_installed(self):
        """
        If a plugin is already installed, it doesn't get downloaded.
        """
        orig_remove_unlisted_plugins = hookenv.config()["remove-unlisted-plugins"]
        try:
            hookenv.config()["remove-unlisted-plugins"] = "yes"
            plugin_path = os.path.join(paths.PLUGINS, "plugin.hpi")
            with open(plugin_path, "w"):
                pass
            self.plugins.install("plugin")
            commands = [proc.args[0] for proc in self.fakes.processes.procs]
            self.assertNotIn("wget", commands)
        finally:
            hookenv.config()["remove-unlisted-plugins"] = orig_remove_unlisted_plugins

    def test_install_bad_plugin(self):
        """
        If plugin can't be downloaded we expect error message in the logs
        """
        def broken_download(*args, **kwargs):
            raise Exception("error")

        self.plugins._install_plugin = broken_download
        orig_remove_unlisted_plugins = hookenv.config()["remove-unlisted-plugins"]
        try:
            hookenv.config()["remove-unlisted-plugins"] = "yes"
            plugin_path = os.path.join(paths.PLUGINS, "bad_plugin.hpi")
            with open(plugin_path, "w"):
                pass
            self.assertRaises(Exception,
                              self.plugins.install, "bad_plugin")
        finally:
            hookenv.config()["remove-unlisted-plugins"] = orig_remove_unlisted_plugins
