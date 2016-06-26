import os

from jenkins import Jenkins

from deployment import (
    DeploymentSpec,
    DeploymentTest,
)

PASSWORD = "test"
PLUGINS_DIR = "/var/lib/jenkins/plugins"


class BasicDeploymentSpec(DeploymentSpec):

    def jenkins_url(self):
        """Get the URL of the Jenkins master."""
        return "http://%s:8080/" % self.jenkins.info["public-address"]

    def plugin_dir_stat(self, plugin):
        """Get the file system stat of the directory of the given plugin."""
        path = os.path.join(PLUGINS_DIR, plugin)
        try:
            stat = self.jenkins.directory_stat(path)
        except IOError:
            stat = None
        return stat

    def plugins_list(self):
        """Get the list of currently installed plugins."""
        contents = self.jenkins.directory_listing(PLUGINS_DIR)
        plugins = []
        for name in contents["files"]:
            if name.endswith(".hpi"):
                plugins.append(name[:-len(".hpi")])
        return plugins

    def _init_00_basic(self):
        self.jenkins_config = {
            "password": PASSWORD,
            "tools": "python3-testtools",
            "plugins": "groovy",
        }

    def _pre_setup_00_basic(self):
        """Set up the deployment in the class."""
        charm_name = self.deployment.charm_name
        # Specify charm_name because this layer could be named something
        # else.
        self.deployment.add(charm_name, units=1)
        self.deployment.configure(charm_name, self.jenkins_config)
        self.deployment.expose("jenkins")

    def _post_setup_00_basic(self):
        self.jenkins = self.deployment.sentry["jenkins"][0]


class BasicDeploymentTest(DeploymentTest):

    def test_00_workload_status(self):
        """Validate initial workload status."""
        status = self.spec.jenkins.info["workload-status"]
        self.assertEqual("active", status["current"])
        self.assertEqual("Jenkins is running", status["message"])

    def test_00_release(self):
        """Validate Jenkins release."""
        sources_list = self.spec.jenkins.file_contents("/etc/apt/sources.list")
        self.assertIn("debian-stable", sources_list, "LTS not in sources.list")

    def test_00_tools_installed(self):
        """Validate jenkins tool installation."""
        output, _ = self.spec.jenkins.run("dpkg -l python3-testtools")
        self.assertIn("ii", output, "No tool installation found")

    def test_00_jenkins_system_user(self):
        """Validate that the jenkins system user exists."""
        # First off, validate that we have the jenkins user on the machine
        _, code = self.spec.jenkins.run("id -u jenkins")
        self.assertEqual(0, code, "No Jenkins system user")

    def test_00_service_running(self):
        """Validate that the jenkins service is running."""
        # First off, validate that we have the jenkins user on the machine
        _, code = self.spec.jenkins.run("service jenkins status")
        self.assertEqual(0, code, "No Jenkins Service Running")

    def test_00_user(self):
        """Validate admin user."""
        client = Jenkins(self.spec.jenkins_url(), "admin", PASSWORD)
        try:
            version = client.get_version()
        except:
            self.fail("Can't access Jenkins API")
        self.assertTrue(version.startswith("1"), "Unexpected Jenkins version")

    def test_00_plugins(self):
        """Validate that configured plugins are installed."""
        # TODO: Figure out how to test installation of NonHTTPS plugins.
        # This is called as a flag to pyjenkins, and I dont know of any non
        # https plugin repositories. Pinned here for reference later.
        stat = self.spec.plugin_dir_stat("groovy")
        self.assertGreater(stat["size"], 0, "Failed to locate plugin")

    def test_10_change_tools(self):
        """Validate that tools are updated after a config change."""
        charm_name = self.spec.deployment.charm_name
        self.spec.deployment.configure(charm_name, {"tools": "python3-lxml"})
        self.spec.deployment.sentry.wait()
        output, _ = self.spec.jenkins.run("dpkg -l python3-testtools")
        self.assertIn("ii", output, "No tool installation found")

    def test_10_change_password(self):
        """Validate that after changing the password we can still login."""
        charm_name = self.spec.deployment.charm_name
        self.spec.deployment.configure(charm_name, {"password": "changed"})
        self.spec.deployment.sentry.wait()
        client = Jenkins(self.spec.jenkins_url(), "admin", "changed")
        try:
            version = client.get_version()
        except:
            self.fail("Can't access Jenkins API")
        self.assertTrue(version.startswith("1"), "Unexpected Jenkins version")

    def test_10_change_plugins(self):
        """Validate that plugins get updated after a config change."""
        plugins = "groovy greenballs"
        charm_name = self.spec.deployment.charm_name
        self.spec.deployment.configure(charm_name, {"plugins": plugins})
        self.spec.deployment.sentry.wait()
        stat = self.spec.plugin_dir_stat("groovy")
        self.assertGreater(stat["size"], 0, "Failed to locate groovy")
        stat = self.spec.plugin_dir_stat("greenballs")
        self.assertGreater(stat["size"], 0, "Failed to locate greenballs")
