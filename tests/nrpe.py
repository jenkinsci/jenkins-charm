from deployment import DeploymentTest
from basic import BasicDeploymentSpec


class NRPEDeploymentSpec(BasicDeploymentSpec):

    def _pre_setup_10_website(self):
        """Set up the deployment in the class."""
        self.deployment.add("nrpe")
        self.deployment.relate("jenkins:nrpe-external-master",
                               "nrpe:nrpe-external-master")


class NRPEDeploymentTest(DeploymentTest):

    def _verify_nrpe(self):
        nrpe_file = '/etc/nagios/nrpe.d/check_jenkins_http.cfg'
        nagios_cmd = "sudo -u nagios $(grep -e " + \
                     "'/usr/lib/nagios/plugins/check_http' " + \
                     "{} | cut -d'=' -f2-)".format(nrpe_file)
        _, return_code = self.spec.jenkins.run(nagios_cmd)
        self.assertEqual(return_code, 0)

    def test_00_nrpe_relation(self):
        """Validate that the Jenkins nagios check is setup."""
        self._verify_nrpe()

    def test_10_nrpe_relation_url_change(self):
        """Validate the Jenkins nagios check after a url change."""
        charm_name = self.spec.deployment.charm_name
        public_url = "http://public.jenkins:8080/jenkins"
        self.spec.deployment.configure(charm_name, {"public-url": public_url})
        self.spec.deployment.sentry.wait()

        self._verify_nrpe()
