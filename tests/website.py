import requests

from deployment import DeploymentTest
from basic import BasicDeploymentSpec


class WebsiteDeploymentSpec(BasicDeploymentSpec):

    def proxy_url(self):
        """Get the URL of haproxy."""
        return "http://%s/" % self.haproxy.info["public-address"]

    def _pre_setup_10_website(self):
        """Set up the deployment in the class."""
        self.deployment.add("haproxy")
        self.deployment.relate("jenkins:website", "haproxy:reverseproxy")
        self.deployment.expose("haproxy")

    def _post_setup_10_website(self):
        self.haproxy = self.deployment.sentry["haproxy"][0]


class WebsiteDeploymentTest(DeploymentTest):

    def test_00_website_relation(self):
        """Validate that Jenkins is correctly reverse-proxied by HAProxy."""
        response = requests.get(self.spec.proxy_url())
        self.assertEqual(403, response.status_code, "Proxy returned non-403")
        self.assertIn(
            "Authentication required", response.text, "Unexpected page")
