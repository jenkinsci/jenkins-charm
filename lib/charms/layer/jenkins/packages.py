import itertools
import os
import os.path
import re
import shutil
import subprocess
import tempfile

from glob import glob
from testtools import try_import
from pkg_resources import parse_version
from charmhelpers.core import hookenv, host
from charms.layer.jenkins import paths

from jenkins_plugin_manager.core import JenkinsCore

# XXX Wrap this import with try_import since layers code won't be available
#     when running unit tests for this layer (and in such case import errors
#     can be safely ignored since we're stubbing out these objects).
apt = try_import("charms.apt")

POSSIBLE_JRE_DEPENDENCIES = {
    "default-jre-headless",
    "openjdk-8-jre-headless",
    "openjdk-11-jre-headless",
}
APT_DEPENDENCIES = {
    "jenkins-2.164-and-later": ["daemon", "openjdk-11-jre-headless"],
    "pre-jenkins-2.164": ["daemon", "openjdk-8-jre-headless"],
}
CONSTANT_APT_DEPENDENCIES = ["daemon"]
APT_SOURCE = "deb http://pkg.jenkins.io/%s binary/"


class Packages(object):
    """Manage Jenkins package dependencies."""

    def __init__(self, apt=apt, ch_host=None):
        """
        @param apt: An object implementing the charms.apt API from the apt
            charm layer (for testing).
        @param ch_host: An object implementing the host API from
            charmhelpers.core (for testing).
        """
        self._apt = apt
        self._host = ch_host or host
        core_url = hookenv.config()["bundle-site"]
        if core_url == "" or core_url == "https://pkg.jenkins.io":
            self._jc = JenkinsCore()
        else:
            self._jc = JenkinsCore(jenkins_core_url=hookenv.config()["bundle-site"])

    def distro_codename(self):
        """Return the distro release code name, e.g. 'precise' or 'trusty'."""
        return self._host.lsb_release()["DISTRIB_CODENAME"]

    def apt_dependencies(self, jenkins_version=None):
        """Get the apt dependencies based on Jenkins version.

        Assumes that, if Jenkins is not installed, that the latest LTS version of Jenkins will be
        installed and returns the dependencies for that version.

        Args:
            jenkins_version: The version of Jenkins to get the apt dependencies for. Based on
                installed Jenkins version if it is None.

        Returns:
            The dependencies of Jenkins to be installed based on the version of Jenkins installed.

        """
        if jenkins_version is None:
            try:
                jenkins_version = self.jenkins_version()
            except subprocess.CalledProcessError:
                # No Jenkins version installed
                pass
        if jenkins_version is not None and parse_version(jenkins_version) < parse_version(
            "2.164.1"
        ):
            return APT_DEPENDENCIES["pre-jenkins-2.164"]
        return APT_DEPENDENCIES["jenkins-2.164-and-later"]

    def install_dependencies(self, jenkins_version=None):
        """Install the deb dependencies of the Jenkins package.

        Removes any dependencies that are no longer needed based on the version of Jenkins to be
        installed and then installs dependencies based on Jenkins version installed/ to be
        installed (assumed to be the latest LTS version if Jenkins is not installed yet).

        Args:
            jenkins_version: The version of Jenkins to get the apt dependencies for. Based on
                installed Jenkins version if it is None.

        """
        hookenv.log("Installing jenkins dependencies and desired tools")

        # Remove any previous dependencies that are no longer needed
        required_apt_dependencies = set(self.apt_dependencies(jenkins_version=jenkins_version))
        self._apt.purge(POSSIBLE_JRE_DEPENDENCIES - required_apt_dependencies)

        # Conditionally install depedencies based on Jenkins version
        self._apt.queue_install(required_apt_dependencies)
        self._apt.install_queued()

    def install_tools(self):
        """Install the configured tools."""
        tools = hookenv.config()["tools"].split()
        self._apt.queue_install(tools)

    def install_jenkins(self):
        """Install the Jenkins package."""
        hookenv.log("Installing jenkins")
        config = hookenv.config()
        release = config["release"]
        if release == "bundle":
            self._install_from_bundle()
        elif release.startswith("http"):
            self._install_from_remote_deb(release)
        else:
            self._setup_source(release)
        self._apt.queue_install(["jenkins"])

    def jenkins_version(self):
        return self._apt.get_package_version("jenkins", full_version=True)

    def _install_from_bundle(self):
        """Install Jenkins from bundled package."""
        config = hookenv.config()
        if config["bundle-site"] == "":
            # Check bundled package exists.
            charm_dir = hookenv.charm_dir()
            bundle_path = os.path.join(charm_dir, "files", "jenkins.deb")
            if not os.path.isfile(bundle_path):
                message = "'%s' doesn't exist. No package bundled." % (bundle_path)
                raise Exception(message)
        else:
            self._jc.jenkins_repo = hookenv.config()["bundle-site"]
            download_path = os.path.join(hookenv.charm_dir(), "files")
            self._bundle_download(download_path)
            bundle_path = os.path.join(download_path, "jenkins_%s_all.deb" % self._jc.core_version)
        hookenv.log("Installing from bundled Jenkins package: %s:" % bundle_path)
        self._install_local_deb(bundle_path)

    def _install_local_deb(self, filename):
        """Install the given local jenkins deb"""
        # Run dpkg to install bundled deb.
        subprocess.check_call(("dpkg", "-i", filename))

    def _install_from_remote_deb(self, url):
        """Install Jenkins from http(s) deb file."""
        hookenv.log("Getting remote jenkins package: %s" % url)
        tempdir = tempfile.mkdtemp()
        target = os.path.join(tempdir, "jenkins.deb")
        subprocess.check_call(("wget", "-q", "-O", target, url))
        self._install_local_deb(target)
        shutil.rmtree(tempdir)

    def _setup_source(self, release):
        """Install Jenkins archive."""
        hookenv.log("Adding upstream '%s' Jenkins APT source " % release)

        # Configure to use upstream archives
        # lts - debian-stable
        # trunk - debian
        if release == "lts":
            dist = "debian-stable"
        elif release == "trunk":
            dist = "debian"
        else:
            message = "Release '%s' configuration not recognised" % (release)
            raise Exception(message)

        # Setup archive to use appropriate jenkins upstream
        source = APT_SOURCE % dist
        keyfile = os.path.join(hookenv.charm_dir(), "jenkins.io.key")
        with open(keyfile, "r") as k:
            key = k.read()
        self._apt.add_source(source, key=key)

    def _bundle_download(self, path=None):
        hookenv.log("Downloading bundle from %s" % self._jc.jenkins_repo)
        self._jc.get_binary_package(path)

    def jenkins_upgradable(self):
        """
        Verify if there's a new version of jenkins available.
        Note: When bundle-site is not set the return will always
        be True.
        """
        if hookenv.config()["bundle-site"] == "":
            return True
        if parse_version(self._jc.core_version) > parse_version(self.jenkins_version()):
            return True
        return False

    def clean_old_plugins(self):
        """
        Remove old plugins directories created by jenkins.deb and old versions
        of this charm.
        """
        hookenv.log("Removing outdated detached plugins from jenkins.deb")
        os.system("sudo rm -r /var/cache/jenkins/war/WEB-INF/detached-plugins")
        hookenv.log("Removing plugins from old charm versions")
        for directory in glob("%s/*/" % paths.PLUGINS):
            os.system("sudo rm -r %s" % directory)
        # Remove plugin files with no version in its name
        for plugin_file in glob("%s/*.jpi" % paths.PLUGINS):
            if not re.search(r"\d\.jpi", plugin_file):
                hookenv.log("Removing old plugin %s" % plugin_file)
                os.system("sudo rm %s" % plugin_file)
