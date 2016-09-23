import os
import shutil
import tempfile
import subprocess

from testtools import try_import

from charmhelpers.core import hookenv

# XXX Wrap this import with try_import since layers code won't be available
#     when running unit tests for this layer (and in such case import errors
#     can be safely ignored since we're stubbing out these objects).
apt = try_import("charms.apt")

APT_DEPENDENCIES = ["daemon", "default-jre-headless"]
APT_SOURCE = "deb http://pkg.jenkins-ci.org/%s binary/"
APT_KEY = "http://pkg.jenkins-ci.org/%s/jenkins-ci.org.key"


class Packages(object):
    """Manage Jenkins package dependencies."""

    def __init__(self, subprocess=subprocess, apt=apt):
        """
        @param subprocess: An object implementing the subprocess API (for
            testing).
        @param apt: An object implementing the charms.apt API from the apt
            charm layer (for testing).
        """
        self._subprocess = subprocess
        self._apt = apt

    def install_dependencies(self):
        """Install the deb dependencies of the Jenkins package."""
        hookenv.log("Installing jenkins dependencies and desired tools")
        self._apt.queue_install(APT_DEPENDENCIES)

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

    def _install_from_bundle(self):
        """Install Jenkins from bundled package."""
        # Check bundled package exists.
        charm_dir = hookenv.charm_dir()
        bundle_path = os.path.join(charm_dir, "files", "jenkins.deb")
        if not os.path.isfile(bundle_path):
            message = "'%s' doesn't exist. No package bundled." % (bundle_path)
            raise Exception(message)
        hookenv.log(
            "Installing from bundled Jenkins package: %s:" % bundle_path)
        self._install_local_deb(bundle_path)

    def _install_local_deb(self, filename):
        """Install the given local jenkins deb"""
        # Run dpkg to install bundled deb.
        self._subprocess.check_call(("dpkg", "-i", filename))

    def _install_from_remote_deb(self, url):
        """Install Jenkins from http(s) deb file."""
        hookenv.log("Getting remote jenkins package: %s" % url)
        tempdir = tempfile.mkdtemp()
        target = os.path.join(tempdir, 'jenkins.deb')
        self._subprocess.check_call(("wget", "-q", "-O", target, url))
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
        wget = ("wget", "-q", "-O", "-", APT_KEY % dist)
        source = APT_SOURCE % dist
        key = self._subprocess.check_output(wget).decode("utf-8")
        self._apt.add_source(source, key=key)
