import os
import shutil
import tempfile
import subprocess

from testtools import try_import

from charmhelpers.core import hookenv

# XXX Wrap these imports with try_import since layers code won't be available
#     when running unit tests for this layer (and in such case import errors
#     can be safely ignored since we're stubbing out these objects).
execd = try_import("charms.layer.execd")
apt = try_import("charms.apt")

APT_JENKINS_DEPS = ["daemon", "adduser", "psmisc", "default-jre"]
APT_JENKINS_SOURCE = "deb http://pkg.jenkins-ci.org/%s binary/"
APT_JENKINS_KEY = "http://pkg.jenkins-ci.org/%s/jenkins-ci.org.key"


class Jenkins(object):
    """Charm-level logic for managing a jenkins unit."""

    def __init__(self, subprocess=subprocess, hookenv=hookenv, execd=execd,
                 apt=apt):
        """
        @param hookenv: An object implementing the charmhelpers.core.hookenv
            API from charmhelpers (for testing).
        @param execd: An object implementing the charms.layer.execd API from
            the basic charm layer (for testing).
        """
        self._subprocess = subprocess
        self._hookenv = hookenv
        self._execd = execd
        self._apt = apt

    def install(self):
        """Install the Jenkins bits."""
        # XXX This is for backward compatibility, since the the pre-layered
        #     version of this charm used a custom exec.d dir, and we want
        #     custom forks of that version to keep working unmodified in
        #     case they merge the code from the new layered charm.
        self._execd.execd_preinstall("hooks/install.d")
        config = self._hookenv.config()
        release = config["release"]
        if release == "bundle":
            self._install_from_bundle()
        elif release.startswith('http'):
            self._install_from_remote_deb(release)
        else:
            self._setup_source(release)

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
        # Install jenkins deps.
        self._apt.queue_install(APT_JENKINS_DEPS)
        # Run dpkg to install bundled deb.
        self._subprocess.check_call(("dpkg", "-i", filename))

    def _install_from_remote_deb(self, link):
        """Install Jenkins from http(s) deb file."""
        self._hookenv.log("Getting remote jenkins package: %s" % link)
        tempdir = tempfile.mkdtemp()
        target = os.path.join(tempdir, 'jenkins.deb')
        self._subprocess.check_call(('wget', '-q', '-O', target, link))
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
        wget = ("wget", "-q", "-O", "-", APT_JENKINS_KEY % dist)
        source = APT_JENKINS_SOURCE % dist
        key = self._subprocess.check_output(wget)
        self._apt.add_source(source, key=key)
