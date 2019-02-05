import os

from charmtest import CharmTest

from charmhelpers.core import hookenv

from stubs.apt import AptStub

from charms.layer.jenkins.packages import (
    APT_DEPENDENCIES,
    APT_SOURCE,
    Packages,
)


class PackagesTest(CharmTest):

    def setUp(self):
        super(PackagesTest, self).setUp()
        self.apt = AptStub()
        self.packages = Packages(apt=self.apt)
        # XXX Not all charm files are populated in charm_dir() by default.
        # XXX See: https://github.com/freeekanayaka/charm-test/issues/2
        keyfile = "jenkins.io.key"
        os.symlink(os.path.join(os.getcwd(), keyfile),
                   os.path.join(hookenv.charm_dir(), keyfile))

    def tearDown(self):
        # Reset installs and sources after each test
        super(PackagesTest, self).tearDown()
        self.packages.installs = []
        self.sources = []

    def test_install_dependencies(self):
        """
        The Jenkins dependencies get installed by the install_dependencies
        method.
        """
        self.packages.install_dependencies()
        self.assertEqual(APT_DEPENDENCIES, self.apt.installs)

    def test_install_tools(self):
        """
        The requested tools get installed by the install_tools method.
        """
        orig_tools = hookenv.config()["tools"]
        try:
            hookenv.config()["tools"] = "git gcc"
            self.packages.install_tools()
            self.assertEqual(["git", "gcc"], self.apt.installs)
        finally:
            hookenv.config()["tools"] = orig_tools

    def test_install_jenkins_bundle(self):
        """
        If the 'release' config is set to 'bundle', then Jenkins will be
        installed from a local jenkins.deb file.
        """
        self.fakes.juju.config["release"] = "bundle"
        files = os.path.join(hookenv.charm_dir(), "files")
        os.mkdir(files)
        bundle_path = os.path.join(files, "jenkins.deb")
        with open(bundle_path, "w") as fd:
            fd.write("")
        self.packages.install_jenkins()
        self.assertEqual(
            ["install"], self.fakes.processes.dpkg.actions["jenkins"])

    def test_install_jenkins_bundle_no_file(self):
        """
        If the 'release' config is set to 'bundle' but no jenkins.deb file is
        present, an error is raised.
        """
        self.fakes.juju.config["release"] = "bundle"
        error = self.assertRaises(Exception, self.packages.install_jenkins)
        path = os.path.join(hookenv.charm_dir(), "files", "jenkins.deb")
        self.assertEqual(
            "'{}' doesn't exist. No package bundled.".format(path),
            str(error))

    def test_install_jenkins_remote(self):
        """
        If the 'release' config is set to a remote URL, then Jenkins will be
        installed from the deb files pointed by that url.
        """
        self.fakes.processes.wget.locations[
            "http://jenkins-1.2.3.deb"] = b"data"
        self.fakes.juju.config["release"] = "http://jenkins-1.2.3.deb"
        self.packages.install_jenkins()
        self.assertEqual(
            ["install"], self.fakes.processes.dpkg.actions["jenkins"])

    def test_install_jenkins_lts_release(self):
        """
        If the 'release' config is set to 'lts', an APT source entry will be
        added, pointing to the debian-stable Jenkins repository.
        """
        self.packages.install_jenkins()
        source = APT_SOURCE % "debian-stable"
        key = os.path.join(hookenv.charm_dir(), "jenkins.io.key")
        with open(key, "r") as k:
            key = k.read()
        self.assertEqual([(source, key)], self.apt.sources)

    def test_install_jenkins_trunk_release(self):
        """
        If the 'release' config is set to 'trunk', an APT source entry will be
        added, pointing to the debian Jenkins repository.
        """
        self.fakes.juju.config["release"] = "trunk"
        self.packages.install_jenkins()
        source = APT_SOURCE % "debian"
        key = os.path.join(hookenv.charm_dir(), "jenkins.io.key")
        with open(key, "r") as k:
            key = k.read()
        self.assertEqual([(source, key)], self.apt.sources)

    def test_install_jenkins_invalid_release(self):
        """
        If the 'release' config is invalid, an error is raised.
        """
        self.fakes.juju.config["release"] = "foo"
        error = self.assertRaises(Exception, self.packages.install_jenkins)
        self.assertEqual(
            "Release 'foo' configuration not recognised", str(error))
