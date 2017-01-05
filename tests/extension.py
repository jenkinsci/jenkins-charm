import requests
import time
from deployment import DeploymentTest
from basic import BasicDeploymentSpec

EXTERNAL = {
    "xenial": "cs:~juju-solutions/cwr-11",
}


class ExtensionDeploymentSpec(BasicDeploymentSpec):

    def _pre_setup_00_extension(self):
        self.deployment.add("cwr", EXTERNAL[self.series])
        self.deployment.relate(
            "jenkins:extension", "cwr:jenkins")
        self.deployment.expose("cwr")

    def _post_setup_00_extension(self):
        self.cwr = self.deployment.sentry["cwr"][0]


class ExtensionDeploymentTest(DeploymentTest):

    def test_00_ping(self):
        """Ping the cwr service."""

        jenkins_ip = self.spec.jenkins.info["public-address"]
        r = requests.get('http://{}:5000/ping'.format(jenkins_ip))
        assert r.status_code is 200

    def test_10_pass_change(self):
        """Change the password and see extensions can still talk to jenkins."""
        ip = self.spec.jenkins.info["public-address"]
        url = 'http://{}:5000/ci/v1.0/trigger/job/RunCwr'.format(ip)

        r = requests.get(url)
        assert r.status_code is 200

        # Change Jenkins password
        charm_name = self.spec.deployment.charm_name
        self.spec.deployment.configure(charm_name, {"password": "changed"})
        self.spec.deployment.sentry.wait()

        # wait for cwr service to see the change and restart
        time.sleep(60)
        # re-trigger the cwr job
        r = requests.get(url)
        assert r.status_code is 200
