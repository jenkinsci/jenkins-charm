#!/usr/bin/env python3

"""
Jenkins Plugin Resolver module.

This module loads the JSON file available in jenkins Update Center
(default https://updates.jenkins.io/stable/update-center.actual.json) and load it for further computation.
"""

import base64
import codecs
import hashlib
import json
import logging
import os
import urllib.request

from packaging import version


logger = logging.getLogger(__name__)


class JUCInvalidVersionError(Exception):
    """Exception when a desired plugin is higher than the most recent one in the Update Center."""

    pass


class JUCInvalidPluginError(Exception):
    """Exception when the desired plugin is invalid or not available."""

    pass


class JUCPluginMinCoreVersionError(Exception):
    """Exception when a plugin need a higher jenkins core version than the one set as the current one."""

    pass


class UpdateCenter(object):
    """Represents the UpdateCenter data."""

    def __init__(
        self,
        uc_url="https://updates.jenkins.io/stable/update-center.json",
        plugin_versions_url="https://updates.jenkins.io/current/plugin-versions.json",
    ):
        """Instanciate the UpdateCenter class.


        """
        self.uc_data = self.load_update_center_data(uc_url)
        # TODO: If handling older plugin is required, the other JSOn is needed
        # self.plugin_versions = self.load_plugin_versions_data(plugin_versions_url)

    def load_update_center_data(self, uc_url):
        """Load the content of the Update Center JSON file.

        :param str uc_url: Update Center JSON file url
        """
        logger.info("Loading Jenkins Update Center data from %s", uc_url)
        with urllib.request.urlopen(uc_url) as uc_data:
            # Remove the "updateCenter.post(\n ... \n);" around the json payload
            json_payload = uc_data.read().decode("utf-8").lstrip("updateCenter.post(\n").rstrip("\n);")
            return json.loads(json_payload)

    # def load_plugin_versions_data(self, plugin_versions_url):
    #     """Load the content of the plugin versions JSON file.

    #     :param str plugin_versions_url: Update Center JSON file url
    #     """
    #     logger.info("Loading Jenkins plugin versions from %s", plugin_versions_url)
    #     with urllib.request.urlopen(plugin_versions_url) as plugin_versions:
    #         return json.loads(plugin_versions.read())

    def get_plugin_data(self, plugin):
        """Return the specific plugin data.

        The plugin can be specificed with "latest" of it's version in the form "<plugin>:(<version>|latest)".
        However, only the latest plugin is pulled. A check is performed to ensure the desired version is inferior or
        equal to the latest available.

        :param str plugin: The name of the plugin, possibly with the version or "latest". e.g  <plugin>:<version>
        :returns: The dictionary of the plugin's data as seen in the Update Center JSON file
        :rtype: dict
        """
        if ":" in plugin:
            plugin_name, plugin_version = plugin.split(":")
        else:
            plugin_name = plugin
            plugin_version = "latest"

        try:
            if plugin_version != "latest":
                # Check that the desired version is <= to the one available in the latest verison of the plugin
                latest_plugin_version = self.uc_data['plugins'][plugin_name]['version']
                if version.parse(plugin_version) > version.parse(latest_plugin_version):
                    err = "Plugin {0} version {1} is higher than the latest available version {2}".format(
                        plugin_name, plugin_version, latest_plugin_version
                    )
                    logger.error(err)
                    raise JUCInvalidVersionError(err)
                elif version.parse(plugin_version) < version.parse(latest_plugin_version):
                    logger.info("Getting %s:%s instead of %s", plugin_name, latest_plugin_version, plugin)

            plugin_data = self.uc_data['plugins'][plugin_name]
            # In case we want to allow an older version, we would need to get the data from this JSON instead
            # plugin_data = self.plugin_versions['plugins'][plugin_name][plugin_version]
            logger.debug("Plugin %s data: %s", plugin_name, plugin_data)
        except KeyError:
            err = "Cannot find plugin {0}".format(plugin_name)
            logger.error(err)
            raise JUCInvalidPluginError(err) from None
        return plugin_data

    def _verify_sha256sum(self, plugin_file_path, sha256sum):
        """Verify the sha256sum of the given file.

        :param str plugin_file_path: Path of the downloaded file
        :param str sha256sum: A base64 encoding of the sha256sum of the plugin
        :returns: True if the file has the right content, False otherwise
        :rtype: bool
        """
        # The sha256 given is a binary base64 that need to be encoded to hex then converted into a string
        # See https://github.com/jenkins-infra/update-center2/blob/master/src/main/java/org/jvnet/hudson/update_center/IndexHtmlBuilder.java#L82 # noqa
        sha256sum_hex = codecs.decode(codecs.encode(base64.b64decode(sha256sum), 'hex'), "utf-8")
        try:
            with open(plugin_file_path, 'rb') as plugin_file:
                content = plugin_file.read()
            sha256sum_check = hashlib.sha256(content).hexdigest()
            if sha256sum_check != sha256sum_hex:
                logger.error("SHA256sum check failed, found %s (expected %s)", sha256sum_check, sha256sum_hex)
                return False
        except FileNotFoundError:
            logger.error("Cannot open the file %s", plugin_file_path)
            return False
        return True

    def _check_min_core_version(self, core_version, plugin_min_core_version):
        """Check the plugin required Jenkins core version.

        :param str core_version: Version of Jenkins core
        :param str plugin_min_core_version: The minimum version of Jenkins core required for this plugin
        :returns: True if the Jenkins core version is sufficient, False otherwise
        :rtype: bool
        """
        if version.parse(core_version) < version.parse(plugin_min_core_version):
            logger.error(
                "Jenkins core version %s or above is required (%s found)", plugin_min_core_version, core_version
            )
            return False
        return True

    def download_plugin(self, plugin, dst_dir, with_version=True):
        """Download the given plugin in the "dst" directory.

        A checksum is done on the files downloaded.

        :param str plugin: The name of the plugin, possibly with the version or "latest". e.g  <plugin>:<version>
        :param str dst: A path where the files are downloaded
        :param bool with_version: Append the version of the plugin to the name in the target file if True.
            Only the name of the plugin if False
        :returns: The path of the downloaded file, False otherwise
        :rtype: str
        """
        plugin_data = self.get_plugin_data(plugin)
        plugin_name = plugin_data['name']

        with urllib.request.urlopen(plugin_data['url']) as plugin_url:
            if with_version:
                plugin_file_path = os.path.join(dst_dir, "{0}-{1}.jpi".format(plugin_name, plugin_data['version']))
            else:
                plugin_file_path = os.path.join(dst_dir, "{0}.jpi".format(plugin_name))
            if not os.path.exists(os.path.dirname(plugin_file_path)):
                os.makedirs(os.path.dirname(plugin_file_path))
            with open(plugin_file_path, "wb") as plugin_file:
                plugin_file.write(plugin_url.read())
        if not self._verify_sha256sum(plugin_file_path, plugin_data['sha256']):
            return False
        logger.info("Plugin %s downloaded to %s", plugin_name, plugin_file_path)
        return plugin_file_path

    def get_plugins_dependencies(self, plugin, optional=False):
        """Get the list of the plugin's dependencies.

        :param str plugin: The name of the plugin, possibly with the version or "latest". e.g  <plugin>:<version>
        :param str dst: A path where the files are downloaded
        :param bool optional: Get the optional dependencies
        :returns: A set of the plugin's dependency
        :rtype: set
        """
        plugin_data = self.get_plugin_data(plugin)
        dependencies_to_fetch = set()
        for dependency in plugin_data['dependencies']:
            # Skip optional dependency  or if already in the list
            if dependency['optional'] and not optional:
                continue
            # Since the constraints are always >=, we don't care to pick up the latest dependency
            dependencies_to_fetch.add(dependency['name'])
        return dependencies_to_fetch

    def get_plugins(self, plugins, current_core_version=None, with_dependency=True, optional=False):
        """Get a list of plugins with their dependencies.

        You can also add optional dependencies if needed.

        :param list plugins: List of plugins to download. Each plugin is a string containing the name of the plugin and
            possibly a colon (":") with the version of the plugin or "latest". If omitted, "latest" is assumed
        :param str current_core_version: Jenkins core version running
        :param bool optional: Add the optional dependencies if True
        :returns: A set of plugins to download
        :rtype: set
        """
        plugins_to_fetch = set()
        dependencies_to_fetch = set()
        for plugin in plugins:
            plugin_data = self.get_plugin_data(plugin)
            plugin_name = plugin_data['name']
            # Check if the Jenkins Core version is enough
            if current_core_version:
                logger.info("Checking minimum Jenkins core version required for %s", plugin)
                if not self._check_min_core_version(current_core_version, plugin_data['requiredCore']):
                    raise JUCPluginMinCoreVersionError(
                        "Plugin {0} requires Jenkins core version {1}".format(plugin_name, plugin_data['requiredCore'])
                    )
            plugins_to_fetch.add(plugin_data['name'])
            if with_dependency:
                dependencies_to_fetch = dependencies_to_fetch.union(self.get_plugins_dependencies(plugin, optional))
        return plugins_to_fetch.union(dependencies_to_fetch)
