import json

import requests

from deployment import DeploymentTest
from basic import BasicDeploymentSpec

JENKINS_SLAVE = {
    "trusty": "cs:~juju-qa/trusty/jenkins-slave-2",
    "xenial": "cs:~free.ekanayaka/xenial/jenkins-slave-2",
}


class SlaveDeploymentSpec(BasicDeploymentSpec):

    def _pre_setup_10_slave(self):
        """Set up the deployment in the class."""
        self.deployment.add("jenkins-slave", JENKINS_SLAVE[self.series])
        self.deployment.relate("jenkins:master", "jenkins-slave:slave")

    def _post_setup_10_slave(self):
        self.jenkins_slave = self.deployment.sentry["jenkins-slave"][0]


class SlaveDeploymentTest(DeploymentTest):

    def test_00_slave_relation(self):
        """Validate that the slave is correctly registered."""
        url = "%s/computer/api/json" % self.spec.jenkins_url()
        response = requests.get(url)
        data = json.loads(response.text)

        node = self.spec.jenkins_slave.info["unit_name"].replace("/", "-")
        self.assertEqual(
            node, data["computer"][1]["displayName"], "Failed to locate slave")
