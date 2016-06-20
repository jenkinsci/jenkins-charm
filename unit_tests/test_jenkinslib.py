import os

from testtools.testcase import TestCase

from fixtures import EnvironmentVariable, TempDir

from stubs.subprocess import SubprocessStub
from stubs.hookenv import HookenvStub
from stubs.execd import ExecdStub
from stubs.apt import AptStub

from jenkinslib import APT_JENKINS_DEPS, APT_JENKINS_KEY, Jenkins


class JenkinsTest(TestCase):

    def setUp(self):
        super(JenkinsTest, self).setUp()
        self.subprocess = SubprocessStub()

        # XXX The charmhelpers.core.hookenv.Config class grabs its path from
        #     the environment, so it's not very test-friendly. Should be fixed
        #     upstream.
        self.charm_dir = self.useFixture(TempDir())
        self.useFixture(EnvironmentVariable("CHARM_DIR", self.charm_dir.path))
        self.hookenv = HookenvStub(self.charm_dir.path)

        self.execd = ExecdStub()
        self.apt = AptStub()

        self.jenkins = Jenkins(
            subprocess=self.subprocess, hookenv=self.hookenv, execd=self.execd,
            apt=self.apt)

    def test_install_custom_preinstall_dir(self):
        """
        The legacy hooks/install.d pre-install directory is still supported.
        """
        self.hookenv.config()["release"] = "lts"
        self.jenkins.install()
        self.assertEqual("hooks/install.d", self.execd.preinstall_dir)

    def test_install_bundle(self):
        """
        If the 'release' config is set to 'bundle', then Jenkins will be
        installed from a local jenkins.deb file.
        """
        self.hookenv.config()["release"] = "bundle"
        os.mkdir(self.charm_dir.join("files"))
        bundle_path = self.charm_dir.join("files", "jenkins.deb")
        with open(bundle_path, "w") as fd:
            fd.write("")
        self.jenkins.install()
        self.assertEqual(APT_JENKINS_DEPS, self.apt.installs)
        [(command, kwargs)] = self.subprocess.calls
        self.assertEqual(("dpkg", "-i", bundle_path), command)

    def test_install_bundle_no_file(self):
        """
        If the 'release' config is set to 'bundle' but no jenkins.deb file is
        present, an error is raised.
        """
        self.hookenv.config()["release"] = "bundle"
        error = self.assertRaises(Exception, self.jenkins.install)
        path = self.charm_dir.join("files", "jenkins.deb")
        self.assertEqual(
            "'{}' doesn't exist. No package bundled.".format(path),
            str(error))

    def test_install_remote(self):
        """
        If the 'release' config is set to a remote URL, then Jenkins will be
        installed from the deb files pointed by that url.
        """
        self.hookenv.config()["release"] = "http://jenkins-1.2.3.deb"
        self.jenkins.install()
        self.assertEqual(APT_JENKINS_DEPS, self.apt.installs)
        [(wget, _), (dpkg, _)] = self.subprocess.calls
        self.assertEqual(("wget", "-q", "-O"), wget[:-2])
        self.assertTrue(wget[-2].endswith("jenkins.deb"))
        self.assertEqual("http://jenkins-1.2.3.deb", wget[-1])
        self.assertEqual(("dpkg", "-i"), dpkg[:-1])
        self.assertTrue(dpkg[-1].endswith("jenkins.deb"))

    def test_install_lts_release(self):
        """
        If the 'release' config is set to 'lts', an APT source entry will be
        added, pointing to the debian-stable Jenkins repository.
        """
        self.hookenv.config()["release"] = "lts"
        self.subprocess.outputs.update({
            ("wget", "-q", "-O", "-", APT_JENKINS_KEY % "debian-stable"): "x"})
        self.jenkins.install()
        self.assertEqual(
            [("deb http://pkg.jenkins-ci.org/debian-stable binary/", "x")],
            self.apt.sources)

    def test_install_trunk_release(self):
        """
        If the 'release' config is set to 'trunk', an APT source entry will be
        added, pointing to the debian Jenkins repository.
        """
        self.hookenv.config()["release"] = "trunk"
        self.subprocess.outputs.update({
            ("wget", "-q", "-O", "-", APT_JENKINS_KEY % "debian"): "x"})
        self.jenkins.install()
        self.assertEqual(
            [("deb http://pkg.jenkins-ci.org/debian binary/", "x")],
            self.apt.sources)

    def test_install_invalid_release(self):
        """
        If the 'release' config is invalid, an error is raised.
        """
        self.hookenv.config()["release"] = "foo"
        error = self.assertRaises(Exception, self.jenkins.install)
        self.assertEqual(
            "Release 'foo' configuration not recognised", str(error))
