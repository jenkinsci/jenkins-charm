import os

from charmfixtures import CharmTest

from stubs.host import HostStub
from stubs.subprocess import SubprocessStub

from charms.layer.jenkins import paths
from charms.layer.jenkins.plugins import Plugins


class PluginsTest(CharmTest):

    def setUp(self):
        super(PluginsTest, self).setUp()
        self.subprocess = SubprocessStub()
        self.host = HostStub()
        self.plugins = Plugins(
            subprocess=self.subprocess, host=self.host)

        self.filesystem.add(paths.PLUGINS)
        self.users.add("jenkins", 123)
        self.groups.add("jenkins", 123)
        self.hooktools.config.update({
            "plugins-site": "https://updates.jenkins-ci.org/latest/",
            "plugins-check-certificate": "yes"})

    def test_install(self):
        """
        The given plugins are downloaded from the Jenkins site.
        """
        self.plugins.install("plugin1 plugin2")
        [action1, action2] = self.host.actions
        self.assertEqual("stop", action1.name)
        self.assertEqual("jenkins", action1.service)
        self.assertEqual("start", action2.name)
        self.assertEqual("jenkins", action2.service)
        [call1, call2] = self.subprocess.calls
        self.assertEqual(
            "wget -q -O - https://updates.jenkins-ci.org/latest/plugin1.hpi",
            " ".join(call1.command))
        self.assertEqual(
            "wget -q -O - https://updates.jenkins-ci.org/latest/plugin2.hpi",
            " ".join(call2.command))

    def test_install_no_certificate_check(self):
        """
        If plugins-check-certificate is set to 'no', the plugins site
        certificate won't be validated.
        """
        self.hooktools.config["plugins-check-certificate"] = "no"
        self.plugins.install("plugin")
        [call] = self.subprocess.calls
        self.assertIn("--no-check-certificate", call.command)

    def test_install_dont_remove_unlisted(self):
        """
        If remove-unlisted-plugins is set to 'yes', then unlisted plugins
        are removed from disk.
        """
        self.hooktools.config["remove-unlisted-plugins"] = "yes"
        unlisted_plugin = os.path.join(paths.plugins(), "unlisted.hpi")
        with open(unlisted_plugin, "w"):
            pass
        self.plugins.install("plugin")
        self.assertFalse(os.path.exists(unlisted_plugin))

    def test_install_do_remove_unlisted(self):
        """
        If remove-unlisted-plugins is set to 'no', then unlisted plugins
        will be left on disk.
        """
        self.hooktools.config["remove-unlisted-plugins"] = "no"
        unlisted_plugin = os.path.join(paths.plugins(), "unlisted.hpi")
        with open(unlisted_plugin, "w"):
            pass
        self.plugins.install("plugin")
        self.assertTrue(os.path.exists(unlisted_plugin))

    def test_install_skip_non_file_unlisted(self):
        """
        If an unlisted plugin is not actually a file, it's just skipped and
        doesn't get removed.
        """
        self.hooktools.config["remove-unlisted-plugins"] = "yes"
        unlisted_plugin = os.path.join(paths.plugins(), "unlisted.hpi")
        os.mkdir(unlisted_plugin)
        self.plugins.install("plugin")
        self.assertTrue(os.path.exists(unlisted_plugin))

    def test_install_already_installed(self):
        """
        If a plugin is already installed, it doesn't get downloaded.
        """
        self.hooktools.config["remove-unlisted-plugins"] = "yes"
        plugin_path = os.path.join(paths.plugins(), "plugin.hpi")
        with open(plugin_path, "w"):
            pass
        self.plugins.install("plugin")
        self.assertEqual([], self.subprocess.calls)
