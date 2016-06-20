import os

from testtools.testcase import TestCase

from fixtures import (
    EnvironmentVariable,
    TempDir,
)

from stubs.subprocess import SubprocessStub
from stubs.hookenv import HookenvStub
from stubs.execd import ExecdStub
from stubs.apt import AptStub
from stubs.host import HostStub
from stubs.templating import TemplatingStub

from jenkinslib import (
    APT_JENKINS_DEPS,
    APT_JENKINS_KEY,
    APT_JENKINS_SOURCE,
    JENKINS_PASSWORD_FILE,
    JENKINS_USERS,
    JENKINS_CONFIG_FILE,
    JenkinsUnit,
)

# SHA256 version of the hard-coded random password from HostStub.password
SALTY_PASSWORD = (
    "eegh5a:3c5eb427399cab549de5139adb70644a7c5580657f6b01f2b2f3380f0f2ce9b7")


class JenkinsUnitTest(TestCase):

    def setUp(self):
        super(JenkinsUnitTest, self).setUp()
        self.subprocess = SubprocessStub()

        # XXX The charmhelpers.core.hookenv.Config class grabs its path from
        #     the environment, so it's not very test-friendly. Should be fixed
        #     upstream.
        self.charm_dir = self.useFixture(TempDir())
        self.useFixture(EnvironmentVariable("CHARM_DIR", self.charm_dir.path))
        self.hookenv = HookenvStub(self.charm_dir.path)

        self.host = HostStub()
        self.templating = TemplatingStub()
        self.execd = ExecdStub()
        self.apt = AptStub()

        self.unit = JenkinsUnit(
            subprocess=self.subprocess, hookenv=self.hookenv, host=self.host,
            templating=self.templating, execd=self.execd, apt=self.apt)

    def test_install_deps(self):
        """
        The Jenkins dependencies get installed by the install_deps method.
        """
        self.unit.install_deps()
        self.assertEqual(APT_JENKINS_DEPS, self.apt.installs)

    def test_install_deps_custom_preinstall_dir(self):
        """
        The legacy hooks/install.d pre-install directory is still supported.
        """
        self.unit.install_deps()
        self.assertEqual("hooks/install.d", self.execd.preinstall_dir)

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
        self.unit.install_jenkins()
        [(command, kwargs)] = self.subprocess.calls
        self.assertEqual(("dpkg", "-i", bundle_path), command)
        self.assertEqual(["jenkins"], self.apt.installs)

    def test_install_jenkins_bundle_no_file(self):
        """
        If the 'release' config is set to 'bundle' but no jenkins.deb file is
        present, an error is raised.
        """
        self.hookenv.config()["release"] = "bundle"
        error = self.assertRaises(Exception, self.unit.install_jenkins)
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
        self.unit.install_jenkins()
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
        key = APT_JENKINS_KEY % "debian-stable"
        self.subprocess.outputs[("wget", "-q", "-O", "-", key)] = b"x"
        self.unit.install_jenkins()
        source = APT_JENKINS_SOURCE % "debian-stable"
        self.assertEqual([(source, "x")], self.apt.sources)

    def test_install_jenkins_trunk_release(self):
        """
        If the 'release' config is set to 'trunk', an APT source entry will be
        added, pointing to the debian Jenkins repository.
        """
        self.hookenv.config()["release"] = "trunk"
        key = APT_JENKINS_KEY % "debian"
        self.subprocess.outputs[("wget", "-q", "-O", "-", key)] = b"x"
        self.unit.install_jenkins()
        source = APT_JENKINS_SOURCE % "debian"
        self.assertEqual([(source, "x")], self.apt.sources)

    def test_install_jenkins_invalid_release(self):
        """
        If the 'release' config is invalid, an error is raised.
        """
        self.hookenv.config()["release"] = "foo"
        error = self.assertRaises(Exception, self.unit.install_jenkins)
        self.assertEqual(
            "Release 'foo' configuration not recognised", str(error))

    def test_configure_admin_user_custom_password(self):
        """
        If a password is provided, it's used to configure the admin user.
        """
        self.hookenv.config()["master-executors"] = 1
        self.hookenv.config()["username"] = "admin"
        self.hookenv.config()["password"] = "sekret"
        self.unit.configure_admin_user()
        password_file = self.host.files[0]
        self.assertEqual(JENKINS_PASSWORD_FILE, password_file.path)
        self.assertEqual(b"sekret", password_file.content)
        self.assertEqual(0o600, password_file.perms)

    def test_configure_admin_user_random_password(self):
        """
        If a password is not provided, a random one will be generated.
        """
        self.hookenv.config()["username"] = "admin"
        self.hookenv.config()["password"] = ""
        self.unit.configure_admin_user()
        password_file = self.host.files[0]
        self.assertEqual(
            self.host.password.encode("utf-8"), password_file.content)

    def test_configure_admin_user_make_users_dir(self):
        """
        The Jenkins user directories are created with proper permissions.
        """
        self.hookenv.config()["username"] = "admin"
        self.hookenv.config()["password"] = ""
        self.unit.configure_admin_user()
        users_dir = self.host.dirs[0]
        admin_user_dir = self.host.dirs[1]
        self.assertEqual(JENKINS_USERS, users_dir.path)
        self.assertEqual("jenkins", users_dir.owner)
        self.assertEqual("nogroup", users_dir.group)
        self.assertEqual(
            os.path.join(JENKINS_USERS, "admin"), admin_user_dir.path)
        self.assertEqual("jenkins", admin_user_dir.owner)
        self.assertEqual("nogroup", admin_user_dir.group)

    def test_configure_admin_write_user_config(self):
        """
        A Jenkins user-config.xml file is written with the appropriate
        details.
        """
        self.hookenv.config()["username"] = "admin"
        self.hookenv.config()["password"] = ""
        self.unit.configure_admin_user()
        render = self.templating.renders[0]
        self.assertEqual("user-config.xml", render.source)
        self.assertEqual(
            os.path.join(JENKINS_USERS, "admin", "config.xml"),
            render.target)
        self.assertEqual(
            {"username": "admin", "password": SALTY_PASSWORD},
            render.context)
        self.assertEqual("jenkins", render.owner)
        self.assertEqual("nogroup", render.group)

    def test_configure_server(self):
        """
        If it hasn't been done yet, the Jenkins configuration file gets
        generated.
        """
        self.hookenv.config()["master-executors"] = 1
        self.unit.configure_server()
        render = self.templating.renders[0]
        self.assertEqual("jenkins-config.xml", render.source)
        self.assertEqual(JENKINS_CONFIG_FILE, render.target)
        self.assertEqual({"master_executors": 1}, render.context)
        self.assertEqual("jenkins", render.owner)
        self.assertEqual("nogroup", render.group)

    def test_configure_server_once(self):
        """
        If it has already been generated, the Jenkins configuration will not
        be touched again.
        """
        self.hookenv.config()["master-executors"] = 1
        self.unit.configure_server()
        self.templating.renders.pop()
        self.unit.configure_server()
        self.assertEqual([], self.templating.renders)

    def test_install_plugins(self):
        """
        The configured plugins are downloaded from the Jenkins site.
        """
        config = self.hookenv.config()
        config["plugins"] = "plugin1 plugin2"
        config["plugins-site"] = "https://updates.jenkins-ci.org/latest/"
        config["plugins-check-certificate"] = "yes"
        self.unit.install_plugins()
        [action1, action2] = self.host.actions
        self.assertEqual("stop", action1.name)
        self.assertEqual("jenkins", action1.service)
        self.assertEqual("start", action2.name)
        self.assertEqual("jenkins", action2.service)
