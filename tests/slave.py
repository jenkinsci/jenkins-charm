from deployment import DeploymentTest
from basic import BasicDeploymentSpec

JENKINS_SLAVE = {
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
        client = self.spec.jenkins_client()
        name = self.spec.jenkins_slave.info["unit_name"].replace("/", "-")
        self.assertIn({"name": name, "offline": False}, client.get_nodes())
