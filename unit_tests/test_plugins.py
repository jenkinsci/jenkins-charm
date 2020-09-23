import os
import urllib
from unittest import mock

from testtools.matchers import (
    PathExists,
    Not,
)

from charmhelpers.core import hookenv

from charmtest import CharmTest

from charms.layer.jenkins import paths
from charms.layer.jenkins.plugins import Plugins


@mock.patch("charms.layer.jenkins.api.Api.restart")
class PluginsTest(CharmTest):

    def setUp(self):
        super(PluginsTest, self).setUp()
        self.plugins = Plugins()

        self.fakes.fs.add(paths.PLUGINS)
        os.makedirs(paths.PLUGINS)
        self.fakes.users.add("jenkins", 123)
        self.fakes.groups.add("jenkins", 123)
        self.orig_plugins_site = hookenv.config()["plugins-site"]
        self.fakes.processes.wget.locations["http://x/plugin.hpi"] = b"data"

    def tearDown(self):
        super(PluginsTest, self).tearDown()
        hookenv.config()["plugins-site"] = self.orig_plugins_site

    def test_remove_plugin(self, mock_restart_jenkins):
        """
        The given plugin file is removed from disk.
        """
        plugin_name = "plugin"
        plugin_path = os.path.join(paths.PLUGINS, "{}-1.jpi".format(plugin_name))
        orig_remove_unlisted_plugins = hookenv.config()["remove-unlisted-plugins"]
        try:
            hookenv.config()["remove-unlisted-plugins"] = "yes"
            with open(plugin_path, "w"):
                pass
            # When using a non-existent path it returns None
            self.assertIsNone(self.plugins._remove_plugin(plugin_name))
            self.plugins._remove_plugin(plugin_path)
            self.assertThat(plugin_path, Not(PathExists()))
        finally:
            hookenv.config()["remove-unlisted-plugins"] = orig_remove_unlisted_plugins

    @mock.patch("test_plugins.Plugins._get_plugins_to_install")
    @mock.patch("charms.layer.jenkins.api.Api.get_plugin_version")
    def test_install(self, mock_get_plugin_version, mock_get_plugins_to_install, mock_restart_jenkins):
        """
        The given plugins are downloaded from the Jenkins site.
        """
        mock_get_plugin_version.return_value = False
        plugin_name = "ansicolor"
        mock_get_plugins_to_install.return_value = {plugin_name}, {}
        installed_plugin = ""
        installed_plugins, incompatible_plugins = self.plugins.install(plugin_name)
        installed_plugin.join(installed_plugins)
        plugin_path = os.path.join(paths.PLUGINS, installed_plugin)
        self.assertTrue(
            os.path.exists(plugin_path),
            msg="Plugin not installed in the proper directory")

        mock_restart_jenkins.assert_called_with()

    @mock.patch("charms.layer.jenkins.api.Api.get_plugin_version")
    @mock.patch("test_plugins.Plugins._get_plugins_to_install")
    def test_install_raises_error(self, mock_get_plugins_to_install, mock_get_plugin_version, mock_restart_jenkins):
        """
        When install fails it should log and raise an error
        """
        def failed_install(*args, **kwargs):
            raise Exception()

        plugin_name = "bad_plugin"
        mock_get_plugins_to_install.return_value = {plugin_name}, {}
        mock_get_plugin_version.return_value = False
        self.plugins._install_plugins = failed_install

        self.assertRaises(Exception, self.plugins.install, plugin_name)
        self.assertEqual(
            "INFO: Plugin installation failed, check logs for details",
            self.fakes.juju.log[-1])
        mock_restart_jenkins.assert_not_called()

    @mock.patch("test_plugins.Plugins._install_plugins")
    @mock.patch("test_plugins.Plugins._get_plugins_to_install")
    def test_install_do_remove_unlisted(self, mock_get_plugins_to_install, mock_install_plugins, mock_restart_jenkins):
        """
        If remove-unlisted-plugins is set to 'yes', then unlisted plugins
        are removed from disk.
        """
        plugin_name = "plugin"
        dependency_plugin_name = "dependency"
        plugin_path = os.path.join(paths.PLUGINS, "{}-1.jpi".format(plugin_name))
        plugin_list = "plugin listed"

        def side_effect(value):
            if value == plugin_list.split():
                fake_result = plugin_list.split()
                fake_result.append(dependency_plugin_name)
                return fake_result
            return {plugin_name, "dependency"}

        mock_get_plugins_to_install.side_effect = side_effect
        mock_install_plugins.return_value = {plugin_path}
        orig_remove_unlisted_plugins = hookenv.config()["remove-unlisted-plugins"]
        orig_plugins = hookenv.config()["plugins"]
        try:
            hookenv.config()["remove-unlisted-plugins"] = "yes"
            hookenv.config()["plugins"] = "plugin listed"
            unlisted_plugin_jpi = os.path.join(paths.PLUGINS, "unlisted.jpi")
            unlisted_plugin_hpi = os.path.join(paths.PLUGINS, "unlisted.hpi")
            listed_plugin = os.path.join(paths.PLUGINS, "listed.jpi")
            dependency_plugin = os.path.join(paths.PLUGINS, "{}.jpi".format(dependency_plugin_name))
            plugin_path = os.path.join(paths.PLUGINS, "{}.jpi".format(plugin_name))
            with open(listed_plugin, "w"):
                pass
            with open(unlisted_plugin_jpi, "w"):
                pass
            with open(unlisted_plugin_hpi, "w"):
                pass
            with open(dependency_plugin, "w"):
                pass
            self.plugins.install(plugin_name)
            # Unlisted plugins should be removed
            self.assertThat(unlisted_plugin_jpi, Not(PathExists()))
            self.assertThat(unlisted_plugin_hpi, Not(PathExists()))
            # Listed plugin should be kept even if they're not being updated
            self.assertThat(listed_plugin, PathExists())
            # Dependency plugins should be kept
            self.assertThat(dependency_plugin, PathExists())

        finally:
            hookenv.config()["remove-unlisted-plugins"] = orig_remove_unlisted_plugins
            hookenv.config()["plugins"] = orig_plugins
            os.remove(listed_plugin)
            os.remove(dependency_plugin)

    @mock.patch("test_plugins.Plugins._remove_plugin")
    @mock.patch("test_plugins.Plugins._install_plugins")
    @mock.patch("test_plugins.Plugins._get_plugins_to_install")
    def test_install_dont_remove_unlisted(self, mock_get_plugins_to_install, mock_install_plugins, mock_remove_plugin, mock_restart_jenkins):
        """
        If remove-unlisted-plugins is set to 'no', then unlisted plugins
        will be left on disk.
        """
        plugin_name = "plugin"
        plugin_path = os.path.join(paths.PLUGINS, "{}-1.jpi".format(plugin_name))
        mock_get_plugins_to_install.return_value = {plugin_name}, {}
        mock_install_plugins.return_value = {plugin_path}
        unlisted_plugin = os.path.join(paths.PLUGINS, "unlisted.jpi")
        unlisted_plugin_path = "{}{}".format(
                self.fakes.fs.root.path, os.path.join(paths.PLUGINS, "unlisted.jpi"))
        with open(unlisted_plugin, "w"):
            pass
        self.plugins.install(plugin_name)
        self.assertEqual(
            "INFO: Unlisted plugins: ({}) Not removed. Set "
            "remove-unlisted-plugins to 'yes' to clear them "
            "away.".format(unlisted_plugin_path), self.fakes.juju.log[-1])
        mock_remove_plugin.assert_not_called()

    @mock.patch("test_plugins.Plugins._install_plugins")
    @mock.patch("test_plugins.Plugins._get_plugins_to_install")
    def test_install_skip_non_file_unlisted(self, mock_get_plugins_to_install, mock_install_plugins,  mock_restart_jenkins):
        """
        If an unlisted plugin is not actually a file, it's just skipped and
        doesn't get removed.
        """
        plugin_name = "plugin"
        mock_get_plugins_to_install.return_value = {plugin_name}, {}
        mock_install_plugins.return_value = {
            os.path.join(paths.PLUGINS, "plugin.jpi")}
        orig_remove_unlisted_plugins = hookenv.config()["remove-unlisted-plugins"]
        try:
            hookenv.config()["remove-unlisted-plugins"] = "yes"
            unlisted_plugin = os.path.join(paths.PLUGINS, "unlisted.hpi")
            os.mkdir(unlisted_plugin)
            self.plugins.install("plugin")
            self.assertThat(unlisted_plugin, PathExists())
        finally:
            hookenv.config()["remove-unlisted-plugins"] = orig_remove_unlisted_plugins

    @mock.patch("test_plugins.Plugins._download_plugin")
    @mock.patch("test_plugins.Plugins._get_latest_version")
    @mock.patch("charms.layer.jenkins.api.Api.get_plugin_version")
    @mock.patch("test_plugins.Plugins._get_plugins_to_install")
    def test_install_already_installed(self, mock_get_plugins_to_install, mock_get_latest_version, mock_get_plugin_version, mock_download_plugin, mock_restart_jenkins):
        """
        If a plugin is already installed, it doesn't get downloaded.
        """
        plugin_name = "plugin"
        mock_get_plugins_to_install.return_value = {plugin_name}, {}
        mock_get_plugin_version.return_value = "1"
        mock_get_latest_version.return_value = "1"
        orig_remove_unlisted_plugins = hookenv.config()["remove-unlisted-plugins"]
        try:
            hookenv.config()["remove-unlisted-plugins"] = "yes"
            hookenv.config()["plugins-auto-update"] = False
            self.plugins.install(plugin_name)
            mock_download_plugin.assert_not_called()
        finally:
            hookenv.config()["remove-unlisted-plugins"] = orig_remove_unlisted_plugins

    def test_install_bad_plugin(self, mock_restart_jenkins):
        """
        If plugin can't be downloaded we expect error message in the logs
        """
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

    @mock.patch("test_plugins.Plugins._download_plugin")
    @mock.patch("test_plugins.Plugins._get_latest_version")
    @mock.patch("charms.layer.jenkins.api.Api.get_plugin_version")
    @mock.patch("test_plugins.Plugins._get_plugins_to_install")
    def test_install_fail(self, mock_get_plugins_to_install, mock_get_plugin_version, mock_get_latest_version, mock_download_plugin, mock_restart_jenkins):
        """If a plugin is already installed, it doesn't get downloaded."""
        plugin_name = "plugin"
        mock_get_plugins_to_install.return_value = {plugin_name}, {}
        mock_get_plugin_version.return_value = False
        mock_get_latest_version.return_value = "1"
        mock_download_plugin.return_value = False
        hookenv.config()["remove-unlisted-plugins"] = "yes"
        self.plugins.install(plugin_name)
        self.assertEqual(
            "INFO: Failed to download plugin",
            self.fakes.juju.log[-1])

    @mock.patch("test_plugins.Plugins._get_plugins_to_install")
    @mock.patch("charms.layer.jenkins.api.Api.get_plugin_version")
    @mock.patch("test_plugins.Plugins._get_latest_version")
    @mock.patch("test_plugins.Plugins._download_plugin")
    def test_update(self, mock_download_plugin, mock_get_latest_version, mock_get_plugin_version, mock_get_plugins_to_install, mock_restart_jenkins):
        """
        The given plugins are installed from the Jenkins site if newer
        versions are available
        """
        plugin_name = "plugin"
        mock_get_plugins_to_install.return_value = {plugin_name}, {}
        mock_get_plugin_version.return_value = "1"
        mock_get_latest_version.return_value = "1.1"
        orig_plugins_auto_update = hookenv.config()["plugins-auto-update"]
        try:
            hookenv.config()["plugins-auto-update"] = True
            self.plugins.update(plugin_name)
            mock_download_plugin.assert_called_with(plugin_name, mock.ANY)
            mock_restart_jenkins.assert_called_with()
        finally:
            hookenv.config()["plugins-auto-update"] = orig_plugins_auto_update

    @mock.patch("test_plugins.Plugins._get_plugins_to_install")
    @mock.patch("charms.layer.jenkins.api.Api.get_plugin_version")
    @mock.patch("test_plugins.Plugins._get_latest_version")
    @mock.patch("test_plugins.Plugins._download_plugin")
    def test_dont_update(self, mock_download_plugin, mock_get_latest_version, mock_get_plugin_version, mock_get_plugins_to_install, mock_restart_jenkins):
        """
        No plugins are reinstalled if not necessary.
        """
        plugin_name = "plugin"
        mock_get_plugins_to_install.return_value = {plugin_name}, {}
        mock_get_plugin_version.return_value = "1"
        mock_get_latest_version.return_value = "1"
        orig_plugins_auto_update = hookenv.config()["plugins-auto-update"]
        try:
            hookenv.config()["plugins-auto-update"] = True
            self.plugins.update(plugin_name)
            mock_download_plugin.assert_not_called()
            self.assertEqual(
                "INFO: No plugins updated",
                self.fakes.juju.log[-1])

        finally:
            hookenv.config()["plugins-auto-update"] = orig_plugins_auto_update

    @mock.patch("charms.layer.jenkins.api.Api.get_plugin_version")
    @mock.patch("test_plugins.Plugins._get_plugins_to_install")
    def test_update_raises_error(self, mock_get_plugins_to_install, mock_get_plugin_version, mock_restart_jenkins):
        """
        When install fails it should log and raise an error
        """
        def failed_install(*args, **kwargs):
            raise Exception()

        plugin_name = "bad_plugin"
        mock_get_plugins_to_install.return_value = {plugin_name}, {}
        mock_get_plugin_version.return_value = False
        self.plugins._install_plugins = failed_install

        self.assertRaises(Exception, self.plugins.update, plugin_name)
        self.assertEqual(
            "INFO: Plugin update failed, check logs for details",
            self.fakes.juju.log[-1])
        mock_restart_jenkins.assert_not_called()

    def test_update_bad_plugin(self, mock_restart_jenkins):
        """
        If plugin can't be downloaded we expect error message in the logs
        """
        def broken_download(*args, **kwargs):
            raise Exception("error")

        self.plugins._install_plugin = broken_download
        plugin_path = os.path.join(paths.PLUGINS, "bad_plugin.hpi")
        with open(plugin_path, "w"):
            pass
        self.assertRaises(Exception,
                          self.plugins.update, "bad_plugin")

    def test_using_json_from_plugin_site(self, mock_restart_jenkins):
        """
        If the configured plugin-site has an update-center.json file,
        it should be used instead of the default one.
        """
        self.plugins = Plugins()
        orig_plugins_site = hookenv.config()["plugins-site"]
        try:
            hookenv.config()["plugins-site"] = "https://updates.jenkins.io/stable/"
            self.plugins = Plugins()
        finally:
            hookenv.config()["plugins-site"] = orig_plugins_site

    def test_broken_json_from_plugin_site(self, mock_restart_jenkins):
        """
        If the configured plugin-site has no update-center.json file,
        it should error.
        """
        orig_plugins_site = hookenv.config()["plugins-site"]
        try:
            hookenv.config()["plugins-site"] = "https://updates.jenkins.io/not-valid/"
            self.assertRaises(Exception, Plugins)
        finally:
            hookenv.config()["plugins-site"] = orig_plugins_site

    @mock.patch("test_plugins.Plugins._get_plugin_info")
    def test__get_required_jenkins(self, mock_get_plugin_info, mock_restart_jenkins):
        plugin_name = "plugin"
        self.plugins._get_required_jenkins(plugin_name)
        mock_get_plugin_info.assert_called_with(plugin_name)

    @mock.patch("test_plugins.Plugins._get_plugins_to_install")
    @mock.patch("charms.layer.jenkins.api.Api.get_plugin_version")
    @mock.patch("test_plugins.Plugins._get_latest_version")
    @mock.patch("test_plugins.Plugins._download_plugin")
    def test_update_incompatible(self, mock_download_plugin, mock_get_latest_version, mock_get_plugin_version, mock_get_plugins_to_install, mock_restart_jenkins):
        """
        Make sure imcompatible plugins are not installed.
        """
        plugin_name = "plugin"
        mock_get_plugins_to_install.return_value = [], [plugin_name]
        mock_get_plugin_version.return_value = "1"
        mock_get_latest_version.return_value = "1.1"
        orig_plugins_auto_update = hookenv.config()["plugins-auto-update"]
        try:
            hookenv.config()["plugins-auto-update"] = True
            updated_plugins, incompatible_plugins = self.plugins.update(plugin_name)
            self.assertEqual(updated_plugins, [])
            self.assertEqual(incompatible_plugins, [plugin_name])
        finally:
            hookenv.config()["plugins-auto-update"] = orig_plugins_auto_update

    @mock.patch("jenkins_plugin_manager.plugin.UpdateCenter.get_plugins")
    @mock.patch("test_plugins.Plugins._get_required_jenkins")
    @mock.patch("charms.layer.jenkins.api.Api.version")
    def test__get_plugins_to_install(self, mock_jenkins_version, mock_get_required_jenkins, mock_get_plugins, mock_restart_jenkins):
        """
        When getting plugins to install all incompatible plugins will be
        removed from the list an returned separatedly.
        """
        plugins = ["plugin_one", "plugin_two"]
        plugins_dependencies = ["plugin_three"]

        def side_effect(value):
            if value == "plugin_one":
                return "2.204"
            if value == "plugin_two":
                return "2.203"
            if value == "plugin_three":
                return "2.203.1"

        mock_jenkins_version.return_value = "2.203"
        mock_get_plugins.return_value = plugins + plugins_dependencies
        mock_get_required_jenkins.side_effect = side_effect

        compatible_plugins, incompatible_plugins = self.plugins._get_plugins_to_install(plugins)
        self.assertEqual(["plugin_two"], compatible_plugins)
        self.assertEqual(["plugin_one", "plugin_three"], incompatible_plugins)

    def test__backup_restore_clean(self, mock_restart_jenkins):
        """Test plugins backing up"""
        self.assertThat(paths.PLUGINS_BACKUP, Not(PathExists()))
        plugin_path = os.path.join(paths.PLUGINS, "plugin")
        with open(plugin_path, "w"):
            pass
        self.plugins.backup()
        os.remove(plugin_path)
        self.assertThat(plugin_path, Not(PathExists()))
        self.assertThat(paths.PLUGINS_BACKUP, PathExists())
        self.plugins.restore()
        self.assertThat(plugin_path, PathExists())
        self.plugins.clean_backup()
        self.assertThat(paths.PLUGINS_BACKUP, Not(PathExists()))
