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

APT_DEPENDENCIES = {
    "xenial": ["daemon", "default-jre-headless"],
    "bionic": ["daemon", "openjdk-8-jre-headless"],
    "focal": ["daemon", "openjdk-8-jre-headless"],
}
APT_SOURCE = "deb http://pkg.jenkins.io/%s binary/"


def _juju_proxy_env():
    proxy_env = {}
    for protocol in ['FTP', 'HTTP', 'HTTPS', 'NO']:
        envvar = '%s_PROXY' % (protocol)
        juju_envvar = 'JUJU_CHARM_%s' % (envvar)
        if juju_envvar in os.environ:
            proxy_env[envvar.lower()] = os.environ[juju_envvar]
    return proxy_env


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
        return self._host.lsb_release()['DISTRIB_CODENAME']

    def install_dependencies(self):
        """Install the deb dependencies of the Jenkins package."""
        hookenv.log("Installing jenkins dependencies and desired tools")
        self._apt.queue_install(APT_DEPENDENCIES[self.distro_codename()])

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
        elif release.startswith('http'):
            self._install_from_remote_deb(release)
        else:
            self._setup_source(release)
        self._apt.queue_install(["jenkins"])

    def jenkins_version(self):
        return self._apt.get_package_version('jenkins', full_version=True)

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
        hookenv.log(
            "Installing from bundled Jenkins package: %s:" % bundle_path)
        self._install_local_deb(bundle_path)

    def _install_local_deb(self, filename):
        """Install the given local jenkins deb"""
        # Run dpkg to install bundled deb.
        subprocess.check_call(("dpkg", "-i", filename))

    def _install_from_remote_deb(self, url):
        """Install Jenkins from http(s) deb file."""
        hookenv.log("Getting remote jenkins package: %s" % url)
        tempdir = tempfile.mkdtemp()
        target = os.path.join(tempdir, 'jenkins.deb')

        proxy_env = _juju_proxy_env()
        try:
            subprocess.check_call(("wget", "-q", "-O", target, url),
                                  env={**os.environ, **proxy_env})
        except subprocess.CalledProcessError: # pragma: no cover
            if len(proxy_env) == 0:
                raise
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
        hookenv.log(
            "Downloading bundle from %s" % self._jc.jenkins_repo)
        self._jc.get_binary_package(path)

    def jenkins_upgradable(self):
        """
            Verify if there's a new version of jenkins available.
            Note: When bundle-site is not set the return will always
            be True.
        """
        if hookenv.config()["bundle-site"] == "":
            return True
        if (parse_version(self._jc.core_version) >
                parse_version(self.jenkins_version())):
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
