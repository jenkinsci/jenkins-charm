import os

from testtools.matchers import (
    PathExists,
    FileContains,
    Not,
)

from charmtest import CharmTest

from charms.layer.jenkins import paths
from charms.layer.jenkins.plugins import Plugins


class PluginsTest(CharmTest):

    def setUp(self):
        super(PluginsTest, self).setUp()
        self.plugins = Plugins()

        self.fakes.fs.add(paths.PLUGINS)
        self.fakes.users.add("jenkins", 123)
        self.fakes.groups.add("jenkins", 123)
        self.fakes.juju.config["plugins-site"] = "http://plugins/"
        self.fakes.network["http://plugins/plugin.hpi"] = b"data"

    def test_install(self):
        """
        The given plugins are downloaded from the Jenkins site.
        """
        self.plugins.install("plugin")
        self.assertEqual(["stop", "start"], self.fakes.services["jenkins"])
        plugin_path = os.path.join(paths.plugins(), "plugin.hpi")
        self.assertThat(plugin_path, FileContains("data"))

    def test_install_no_certificate_check(self):
        """
        If plugins-check-certificate is set to 'no', the plugins site
        certificate won't be validated.
        """
        self.fakes.juju.config["plugins-check-certificate"] = "no"
        self.plugins.install("plugin")
        self.assertIn(
            "--no-check-certificate", self.fakes.processes.procs[-4].args)

    def test_install_dont_remove_unlisted(self):
        """
        If remove-unlisted-plugins is set to 'yes', then unlisted plugins
        are removed from disk.
        """
        self.fakes.juju.config["remove-unlisted-plugins"] = "yes"
        unlisted_plugin = os.path.join(paths.plugins(), "unlisted.hpi")
        with open(unlisted_plugin, "w"):
            pass
        self.plugins.install("plugin")
        self.assertThat(unlisted_plugin, Not(PathExists()))

    def test_install_do_remove_unlisted(self):
        """
        If remove-unlisted-plugins is set to 'no', then unlisted plugins
        will be left on disk.
        """
        unlisted_plugin = os.path.join(paths.plugins(), "unlisted.hpi")
        with open(unlisted_plugin, "w"):
            pass
        self.plugins.install("plugin")
        self.assertThat(unlisted_plugin, PathExists())

    def test_install_skip_non_file_unlisted(self):
        """
        If an unlisted plugin is not actually a file, it's just skipped and
        doesn't get removed.
        """
        self.fakes.juju.config["remove-unlisted-plugins"] = "yes"
        unlisted_plugin = os.path.join(paths.plugins(), "unlisted.hpi")
        os.mkdir(unlisted_plugin)
        self.plugins.install("plugin")
        self.assertThat(unlisted_plugin, PathExists())

    def test_install_already_installed(self):
        """
        If a plugin is already installed, it doesn't get downloaded.
        """
        self.fakes.juju.config["remove-unlisted-plugins"] = "yes"
        plugin_path = os.path.join(paths.plugins(), "plugin.hpi")
        with open(plugin_path, "w"):
            pass
        self.plugins.install("plugin")
        commands = [proc.args[0] for proc in self.fakes.processes.procs]
        self.assertNotIn("wget", commands)
