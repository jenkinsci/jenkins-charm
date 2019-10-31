import json
import os
import tempfile
import unittest

from unittest import mock

import jenkins_plugin_resolver

from jenkins_plugin_resolver import UpdateCenter

UC_DATA_FILE = "update_center_data.json"
PLUGIN_VERSIONS_FILE = "plugin_versions.json"


class TestUpdateCenterLoad(unittest.TestCase):
    """Tests for the UpdateCenter methods loading data."""

    dir_path = os.path.dirname(os.path.realpath(__file__))
    uc_data_file = os.path.join(dir_path, UC_DATA_FILE)
    with open(uc_data_file, "r") as uc_data:
        uc_data = uc_data.read()
    # plugin_versions_file = os.path.join(dir_path, PLUGIN_VERSIONS_FILE)
    # with open(plugin_versions_file, "r") as plugin_versions:
    #     plugin_versions = plugin_versions.read()

    @mock.patch("urllib.request.urlopen", autospec=True)
    def test_load_update_center_data(self, urllib_mock):
        cm = mock.MagicMock()
        cm.read.return_value = "updateCenter.post(\n{0}\n);".format(self.uc_data).encode("utf-8")
        cm.__enter__.return_value = cm
        urllib_mock.return_value = cm
        uc = UpdateCenter()
        self.assertEqual(uc.uc_data, json.loads(self.uc_data))


class TestUpdateCenter(unittest.TestCase):
    """Tests for the UpdateCenter class and methods."""

    dir_path = os.path.dirname(os.path.realpath(__file__))
    uc_data_file = os.path.join(dir_path, UC_DATA_FILE)
    with open(uc_data_file, "r") as uc_data:
        uc_data = json.loads(uc_data.read())
    # plugin_versions_file = os.path.join(dir_path, PLUGIN_VERSIONS_FILE)
    # with open(plugin_versions_file, "r") as plugin_versions:
    #     plugin_versions = json.loads(plugin_versions.read())

    # @mock.patch('jenkins_plugin_resolver.UpdateCenter.load_plugin_versions_data')
    # def setUp(self, uc_data_mock, plugin_versions_mock):
    @mock.patch('jenkins_plugin_resolver.UpdateCenter.load_update_center_data')
    def setUp(self, uc_data_mock):
        """Load samples of the Jenkins UpdateCenter JSON files."""
        self.uc_data_mock = uc_data_mock
        self.uc_data_mock.return_value = self.uc_data
        # self.plugin_versions_mock = plugin_versions_mock
        # self.plugin_versions_mock.return_value = self.plugin_versions
        self.uc = UpdateCenter()

    def tearDown(self):
        """Reset the mocks after each test."""
        self.uc_data_mock.reset_mock()
        # self.plugin_versions_mock.reset_mock()

    def test_default_load_data(self):
        """Test the default JSON files."""
        self.uc_data_mock.assert_called_once_with("https://updates.jenkins.io/stable/update-center.json")
        # self.plugin_versions_mock.assert_called_once_with("https://updates.jenkins.io/current/plugin-versions.json")

        self.uc_data_mock.reset_mock()
        # self.plugin_versions_mock.reset_mock()

    # @mock.patch('jenkins_plugin_resolver.UpdateCenter.load_plugin_versions_data')
    # def test_custom_load_data(self, custom_uc_data_mock, custom_plugin_versions_mock):
    @mock.patch('jenkins_plugin_resolver.UpdateCenter.load_update_center_data')
    def test_custom_load_data(self, custom_uc_data_mock):
        """Test custom urls for JSON files."""
        custom_uc_data_mock.return_value = self.uc_data
        # custom_plugin_versions_mock.return_value = self.plugin_versions
        UpdateCenter(
            uc_url="http://archive.admin.canonical.com/others/stable/update-center.json",
            plugin_versions_url="http://archive.admin.canonical.com/others/stable/plugin-versions.json",
        )
        custom_uc_data_mock.assert_called_once_with(
            "http://archive.admin.canonical.com/others/stable/update-center.json"
        )
        # custom_plugin_versions_mock.assert_called_once_with(
        #     "http://archive.admin.canonical.com/others/stable/plugin-versions.json"
        # )

    def test_get_plugin_data(self):
        """Test the plugin data and the exception raised."""
        plugin_test = "ansible"
        plugin_data = self.uc.get_plugin_data(plugin_test)
        self.assertEqual(plugin_data, self.uc_data['plugins'][plugin_test])
        plugin_test = "PluginThatDoesNotExist"
        with self.assertRaises(jenkins_plugin_resolver.JUCInvalidPluginError):
            self.uc.get_plugin_data(plugin_test)
        plugin_test = "docker-workflow:999999"
        with self.assertRaises(jenkins_plugin_resolver.JUCInvalidVersionError):
            plugin_data = self.uc.get_plugin_data(plugin_test)
        plugin_test = "docker-workflow:1.20"
        with self.assertLogs(logger='jenkins_plugin_resolver', level='INFO') as cm:
            plugin_data = self.uc.get_plugin_data(plugin_test)
        self.assertEqual(plugin_data['version'], "1.21")
        self.assertEqual(
            cm.output, ["INFO:jenkins_plugin_resolver:Getting docker-workflow:1.21 instead of docker-workflow:1.20"]
        )

    @unittest.skip("Cannot figure why the mock_open doesn't work")
    def test_verify_sha256sum(self):
        """Test the weird sha256sum.

        Fake a file containing "Jenkins Plugin Resolver Rocks!" for the check
        sha256sum = 364c0f21c64e4ccaafb82dddea6a3c5db27386bd9925d14e703fc396ab67a7b4
        The sha256sum expected as argument is NkwPIcZOTMqvuC3d6mo8XbJzhr2ZJdFOcD/Dlqtnp7Q=
        """
        with mock.patch(
            "builtins.open", mock.mock_open(read_data="Jenkins Plugin Resolver Rocks!".encode("utf-8")), create=True
        ) as m:
            check = self.uc._verify_sha256sum("/var/tmp/check", "NkwPIcZOTMqvuC3d6mo8XbJzhr2ZJdFOcD/Dlqtnp7Q=")
        self.assertTrue(check)
        m.assert_called_once_with("/var/tmp/check")

    def test_check_min_core_version(self):
        """Test the required Jenkins core version is available."""
        with self.assertLogs(logger='jenkins_plugin_resolver', level='ERROR') as cm:
            self.assertFalse(self.uc._check_min_core_version('2.1', '2.190.1'))
            self.assertEqual(
                cm.output,
                ["ERROR:jenkins_plugin_resolver:Jenkins core version 2.190.1 or above is required (2.1 found)"],
            )
        self.assertTrue(self.uc._check_min_core_version('2.190.1', '2.190'))

    @mock.patch("jenkins_plugin_resolver.UpdateCenter.get_plugin_data")
    @mock.patch("jenkins_plugin_resolver.UpdateCenter._verify_sha256sum", autospec=True)
    @mock.patch("urllib.request.urlopen", autospec=True)
    def test_download_plugin(self, urllib_mock, checksum_mock, get_plugin_data_mock):
        """Test the download of a plugin."""

        def get_plugin_data(plugin):
            return self.uc_data['plugins'][plugin]

        cm = mock.MagicMock()
        cm.read.return_value = b"This is a plugin"
        cm.__enter__.return_value = cm
        urllib_mock.return_value = cm
        checksum_mock.return_value = True
        get_plugin_data_mock.side_effect = get_plugin_data
        with tempfile.TemporaryDirectory() as test_dir:
            plugin_file = os.path.join(test_dir, "jenkins", "ansicolor-0.6.2.jpi")
            with self.assertLogs(logger='jenkins_plugin_resolver', level='INFO') as cm:
                filepath = self.uc.download_plugin("ansicolor", os.path.join(test_dir, "jenkins"))
            self.assertTrue(os.path.exists(os.path.join(test_dir, "jenkins")))
            self.assertEqual(filepath, plugin_file)
            self.assertEqual(
                cm.output, ["INFO:jenkins_plugin_resolver:Plugin ansicolor downloaded to {0}".format(plugin_file)]
            )
            # Check that when verify_sha256sum fails, return False
            checksum_mock.return_value = False
            self.assertFalse(self.uc.download_plugin("ant", os.path.join(test_dir, "jenkins"), with_version=False))
            self.assertFalse(os.path.exists(os.path.join(test_dir, "jenkins", "ant-1.10.jpi")))
            self.assertTrue(os.path.exists(os.path.join(test_dir, "jenkins", "ant.jpi")))

    def test_get_plugin_dependencies(self):
        """Test the list of dependencies for a given plugin."""
        # Should be empty because all dependencies are optional
        deps = self.uc.get_plugins_dependencies("ansicolor")
        self.assertEqual(set(), deps)
        deps = self.uc.get_plugins_dependencies("ansicolor", optional=True)
        self.assertEqual({"workflow-api", "workflow-step-api"}, deps)

    def test_get_plugins(self):
        """Test the list of plugins to fetch and the check with the current Jenkins core version."""
        with self.assertRaises(jenkins_plugin_resolver.JUCPluginMinCoreVersionError):
            self.uc.get_plugins(["ansicolor"], current_core_version="2.144")
        plugins = self.uc.get_plugins(["ant"])
        self.assertEqual(plugins, {"ant", "structs"})
