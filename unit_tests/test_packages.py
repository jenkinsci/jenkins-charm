import os

from testtools.testcase import TestCase

from fixtures import (
    EnvironmentVariable,
    TempDir,
)

from stubs.subprocess import SubprocessStub
from stubs.hookenv import HookenvStub
from stubs.apt import AptStub

from packages import (
    APT_DEPENDENCIES,
    APT_KEY,
    APT_SOURCE,
    Packages,
)


class PackagesTest(TestCase):

    def setUp(self):
        super(PackagesTest, self).setUp()
        self.subprocess = SubprocessStub()
        self.charm_dir = self.useFixture(TempDir())
        self.useFixture(EnvironmentVariable("CHARM_DIR", self.charm_dir.path))
        self.hookenv = HookenvStub(self.charm_dir.path)
        self.hookenv.config()["tools"] = ""
        self.apt = AptStub()

        self.packages = Packages(
            subprocess=self.subprocess, hookenv=self.hookenv, apt=self.apt)

    def test_install_dependencies(self):
        """
        The Jenkins dependencies get installed by the install_dependencies
        method.
        """
        self.packages.install_dependencies()
        self.assertEqual(APT_DEPENDENCIES, self.apt.installs)

    def test_install_dependencies_with_tools(self):
        """
        If extra tools are specified in the config, they are installed as well.
        """
        self.hookenv.config()["tools"] = "git gcc"
        self.packages.install_dependencies()
        self.assertEqual(APT_DEPENDENCIES + ["git", "gcc"], self.apt.installs)

    def test_install_jenkins_bundle(self):
        """
        If the 'release' config is set to 'bundle', then Jenkins will be
        installed from a local jenkins.deb file.
        """
        self.hookenv.config()["release"] = "bundle"
        os.mkdir(self.charm_dir.join("files"))
        bundle_path = self.charm_dir.join("files", "jenkins.deb")
        with open(bundle_path, "w") as fd:
            fd.write("")
        self.packages.install_jenkins()
        [(command, kwargs)] = self.subprocess.calls
        self.assertEqual(("dpkg", "-i", bundle_path), command)
        self.assertEqual(["jenkins"], self.apt.installs)

    def test_install_jenkins_bundle_no_file(self):
        """
        If the 'release' config is set to 'bundle' but no jenkins.deb file is
        present, an error is raised.
        """
        self.hookenv.config()["release"] = "bundle"
        error = self.assertRaises(Exception, self.packages.install_jenkins)
        path = self.charm_dir.join("files", "jenkins.deb")
        self.assertEqual(
            "'{}' doesn't exist. No package bundled.".format(path),
            str(error))

    def test_install_jenkins_remote(self):
        """
        If the 'release' config is set to a remote URL, then Jenkins will be
        installed from the deb files pointed by that url.
        """
        self.hookenv.config()["release"] = "http://jenkins-1.2.3.deb"
        self.packages.install_jenkins()
        [(wget, _), (dpkg, _)] = self.subprocess.calls
        self.assertEqual(("wget", "-q", "-O"), wget[:3])
        self.assertTrue(wget[3].endswith("jenkins.deb"))
        self.assertEqual("http://jenkins-1.2.3.deb", wget[4])
        self.assertEqual(("dpkg", "-i"), dpkg[:-1])
        self.assertTrue(dpkg[-1].endswith("jenkins.deb"))

    def test_install_jenkins_lts_release(self):
        """
        If the 'release' config is set to 'lts', an APT source entry will be
        added, pointing to the debian-stable Jenkins repository.
        """
        self.hookenv.config()["release"] = "lts"
        key = APT_KEY % "debian-stable"
        self.subprocess.outputs[("wget", "-q", "-O", "-", key)] = b"x"
        self.packages.install_jenkins()
        source = APT_SOURCE % "debian-stable"
        self.assertEqual([(source, "x")], self.apt.sources)

    def test_install_jenkins_trunk_release(self):
        """
        If the 'release' config is set to 'trunk', an APT source entry will be
        added, pointing to the debian Jenkins repository.
        """
        self.hookenv.config()["release"] = "trunk"
        key = APT_KEY % "debian"
        self.subprocess.outputs[("wget", "-q", "-O", "-", key)] = b"x"
        self.packages.install_jenkins()
        source = APT_SOURCE % "debian"
        self.assertEqual([(source, "x")], self.apt.sources)

    def test_install_jenkins_invalid_release(self):
        """
        If the 'release' config is invalid, an error is raised.
        """
        self.hookenv.config()["release"] = "foo"
        error = self.assertRaises(Exception, self.packages.install_jenkins)
        self.assertEqual(
            "Release 'foo' configuration not recognised", str(error))
