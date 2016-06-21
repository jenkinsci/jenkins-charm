import os
import shutil
import tempfile
import subprocess

from testtools import try_import

from charmhelpers.core import hookenv
from charmhelpers.core.hookenv import DEBUG

# XXX Wrap these imports with try_import since layers code won't be available
#     when running unit tests for this layer (and in such case import errors
#     can be safely ignored since we're stubbing out these objects).
apt = try_import("charms.apt")

APT_DEPENDENCIES = ["python-jenkins", "daemon", "default-jre-headless"]
APT_SOURCE = "deb http://pkg.jenkins-ci.org/%s binary/"
APT_KEY = "http://pkg.jenkins-ci.org/%s/jenkins-ci.org.key"


class Packages(object):

    def __init__(self, subprocess=subprocess, hookenv=hookenv, apt=apt):
        self._subprocess = subprocess
        self._apt = apt
        self._hookenv = hookenv

    def install_dependencies(self):
        """Install the deb dependencies of the Jenkins package."""
        self._hookenv.log("Installing jenkins dependencies.", level=DEBUG)
        tools = self._hookenv.config()["tools"]
        self._apt.queue_install(APT_DEPENDENCIES + tools.split())

    def install_jenkins(self):
        """Install the Jenkins package."""
        self._hookenv.log("Installing jenkins.", level=DEBUG)
        config = self._hookenv.config()
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
        charm_dir = self._hookenv.charm_dir()
        bundle_path = os.path.join(charm_dir, "files", "jenkins.deb")
        if not os.path.isfile(bundle_path):
            message = "'%s' doesn't exist. No package bundled." % (bundle_path)
            raise Exception(message)
        self._hookenv.log(
            "Installing from bundled Jenkins package: %s:" % bundle_path)
        self._install_local_deb(bundle_path)

    def _install_local_deb(self, filename):
        """Install the given local jenkins deb"""
        # Run dpkg to install bundled deb.
        self._subprocess.check_call(("dpkg", "-i", filename))

    def _install_from_remote_deb(self, url):
        """Install Jenkins from http(s) deb file."""
        self._hookenv.log("Getting remote jenkins package: %s" % url)
        tempdir = tempfile.mkdtemp()
        target = os.path.join(tempdir, 'jenkins.deb')
        self._subprocess.check_call(("wget", "-q", "-O", target, url))
        self._install_local_deb(target)
        shutil.rmtree(tempdir)

    def _setup_source(self, release):
        """Install Jenkins archive."""
        self._hookenv.log("Configuring source of jenkins as %s" % release)

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
