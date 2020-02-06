import os

from glob import glob
from unittest import mock

from testtools.matchers import (
    PathExists,
    Not,
)

from charmtest import CharmTest

from charmhelpers.core import hookenv

from charms.layer.jenkins import paths

from stubs.apt import AptStub
from stubs.host import CharmHelpersCoreHostStub

from charms.layer.jenkins.packages import (
    APT_DEPENDENCIES,
    APT_SOURCE,
    Packages,
)


class PackagesTest(CharmTest):

    def setUp(self):
        super(PackagesTest, self).setUp()
        self.apt = AptStub()
        self.ch_host = CharmHelpersCoreHostStub()
        self.packages = Packages(apt=self.apt, ch_host=self.ch_host)
        # XXX Not all charm files are populated in charm_dir() by default.
        # XXX See: https://github.com/freeekanayaka/charm-test/issues/2
        keyfile = "jenkins.io.key"
        os.symlink(os.path.join(os.getcwd(), keyfile),
                   os.path.join(hookenv.charm_dir(), keyfile))

        jenkins_cache_dir = "/var/cache/jenkins/war/WEB-INF"
        self.fakes.fs.add(paths.PLUGINS)
        self.fakes.fs.add(jenkins_cache_dir)
        os.makedirs(paths.PLUGINS)
        os.makedirs(jenkins_cache_dir)

    def tearDown(self):
        # Reset installs and sources after each test
        super(PackagesTest, self).tearDown()
        self.packages.installs = []
        self.packages.sources = []

    def test_install_dependencies(self):
        """
        The Jenkins dependencies get installed by the install_dependencies
        method.
        """
        # Our default distro version (xenial).
        self.assertEqual(self.packages.distro_codename(), 'xenial')
        self.packages.install_dependencies()
        self.assertEqual(APT_DEPENDENCIES['xenial'], self.apt.installs)
        # Now check with a distro of bionic.
        self.apt.installs = []
        self.ch_host._set_distro_version('bionic')
        self.assertEqual(self.packages.distro_codename(), 'bionic')
        self.packages.install_dependencies()
        self.assertEqual(APT_DEPENDENCIES['bionic'], self.apt.installs)

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
        orig_release = hookenv.config()["release"]
        try:
            hookenv.config()["release"] = "bundle"
            files = os.path.join(hookenv.charm_dir(), "files")
            os.mkdir(files)
            bundle_path = os.path.join(files, "jenkins.deb")
            with open(bundle_path, "w") as fd:
                fd.write("")
            self.packages.install_jenkins()
            self.assertEqual(
                ["install"], self.fakes.processes.dpkg.actions["jenkins"])
        finally:
            hookenv.config()["release"] = orig_release

    def test_install_jenkins_bundle_no_file(self):
        """
        If the 'release' config is set to 'bundle' but no jenkins.deb file is
        present, an error is raised.
        """
        orig_release = hookenv.config()["release"]
        try:
            hookenv.config()["release"] = "bundle"
            path = os.path.join(hookenv.charm_dir(), "files", "jenkins.deb")
            self.assertThat(path, Not(PathExists()))
            error = self.assertRaises(Exception, self.packages._install_from_bundle)
            self.assertEqual(
                "'{}' doesn't exist. No package bundled.".format(path),
                str(error))
        finally:
            hookenv.config()["release"] = orig_release

    def test_install_jenkins_remote(self):
        """
        If the 'release' config is set to a remote URL, then Jenkins will be
        installed from the deb files pointed by that url.
        """
        self.fakes.processes.wget.locations[
            "http://jenkins-1.2.3.deb"] = b"data"
        orig_release = hookenv.config()["release"]
        try:
            hookenv.config()["release"] = "http://jenkins-1.2.3.deb"
            self.packages.install_jenkins()
            self.assertEqual(
                ["install"], self.fakes.processes.dpkg.actions["jenkins"])
        finally:
            hookenv.config()["release"] = orig_release

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
        orig_release = hookenv.config()["release"]
        try:
            hookenv.config()["release"] = "trunk"
            self.packages.install_jenkins()
            source = APT_SOURCE % "debian"
            key = os.path.join(hookenv.charm_dir(), "jenkins.io.key")
            with open(key, "r") as k:
                key = k.read()
            self.assertEqual([(source, key)], self.apt.sources)
        finally:
            hookenv.config()["release"] = orig_release

    def test_install_jenkins_invalid_release(self):
        """
        If the 'release' config is invalid, an error is raised.
        """
        orig_release = hookenv.config()["release"]
        try:
            hookenv.config()["release"] = "foo"
            error = self.assertRaises(Exception, self.packages.install_jenkins)
            self.assertEqual(
                "Release 'foo' configuration not recognised", str(error))
        finally:
            hookenv.config()["release"] = orig_release

    def test_jenkins_version(self):
        self.assertEqual(self.packages.jenkins_version(), '2.150.1')
        # And now test older version.
        self.apt._set_jenkins_version('2.128.1')
        self.assertEqual(self.packages.jenkins_version(), '2.128.1')

    def test_jenkins_upgradable_without_bundle_site(self):
        """
        Jenkins should always be upgradable when bundle-site
        isn't set.
        """
        self.assertTrue(self.packages.jenkins_upgradable())
        self.apt._set_jenkins_version('2.128.1')
        self.packages._jc.core_version = '2.128.1'
        self.assertTrue(self.packages.jenkins_upgradable())

    @mock.patch("charms.layer.jenkins.packages.JenkinsCore")
    def test_jenkins_upgradable_with_bundle_site(self, mock_jenkins_core_version):
        """
        If the latest jenkins package version available in bundle-site is
        higher than the installed one, jenkins will be upgradable.
        """
        orig_bundle_site = hookenv.config()["bundle-site"]
        try:
            hookenv.config()["bundle-site"] = "http://test"
            self.packages = Packages(apt=self.apt, ch_host=self.ch_host)
            self.apt._set_jenkins_version('2.128.1')
            self.packages._jc.core_version = '2.128.2'
            self.assertTrue(self.packages.jenkins_upgradable())
            self.packages._jc.core_version = '2.128.1'
            self.assertFalse(self.packages.jenkins_upgradable())
        finally:
            hookenv.config()["bundle-site"] = orig_bundle_site

    def test_bundle_download(self):
        bundle_path = os.path.join(hookenv.charm_dir(), "jenkins.deb")
        self.packages._bundle_download(bundle_path)
        self.assertThat(bundle_path, PathExists())

    def test_install_jenkins_bundle_download(self):
        """
        If the 'release' config is set to 'bundle' and bundle-site is set,
        then Jenkins will be downloaded and installed from bundle-site.
        """
        orig_release = hookenv.config()["release"]
        orig_bundle_site = hookenv.config()["bundle-site"]
        try:
            hookenv.config()["release"] = "bundle"
            hookenv.config()["bundle-site"] = "https://pkg.jenkins.io"
            bundle_path = os.path.join(hookenv.charm_dir(), "files")
            self.packages.install_jenkins()
            self.assertTrue(glob('%s/jenkins_*.deb' % bundle_path))
            self.assertEqual(
                ["install"], self.fakes.processes.dpkg.actions["jenkins"])
        finally:
            hookenv.config()["release"] = orig_release
            hookenv.config()["bundle-site"] = orig_bundle_site
    @mock.patch("charms.layer.jenkins.packages.os.system")
    def test_clean_old_plugins(self, mock_os_system):
        """
        Make sure old plugin directories are excluded.
        """
        plugins = ["test1_plugin", "test2_plugin", "test3_plugin"]
        kept_plugins = []
        detached_plugins_dir = "/var/cache/jenkins/war/WEB-INF/detached-plugins"
        os_expected_calls = [mock.call("sudo rm -r %s" % detached_plugins_dir)]

        os.mkdir(detached_plugins_dir)
        for plugin in plugins:
            # Create old plugins directories and .jpi files with no version
            plugin_dir = os.path.join(paths.PLUGINS, plugin)
            plugin_file = os.path.join(paths.PLUGINS, "%s.jpi" % plugin)
            os.mkdir(plugin_dir)
            with open(plugin_file, "w") as fd:
                fd.write("")
            # And expect them to be removed
            os_expected_calls.append(mock.call("sudo rm -r %s/" % plugin_dir))
            os_expected_calls.append(mock.call("sudo rm %s" % plugin_file))

            # Create plugins with version that should not be removed
            plugin_to_keep = os.path.join(paths.PLUGINS, "%s-1.jpi" % plugin)
            kept_plugins.append(plugin_to_keep)
            with open(plugin_to_keep, "w") as fd:
                fd.write("")

        self.packages.clean_old_plugins()
        self.assertThat(paths.PLUGINS, PathExists())
        self.assertCountEqual(mock_os_system.mock_calls, os_expected_calls)
        mock_os_system.assert_has_calls(os_expected_calls, any_order=True)
