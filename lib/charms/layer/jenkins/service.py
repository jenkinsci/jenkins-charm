import requests

from charmhelpers.core.decorators import retry_on_exception

from charms.layer.jenkins.api import Api


class ServiceUnavailable(Exception):
    """Raised internally by check_ready() if the service is not ready."""


class Service(object):
    """Interact with the jenkins system service."""

    _check_ready_retry = (requests.ConnectionError, ServiceUnavailable)

    # Wait up to 140 seconds for Jenkins to be fully up.
    @retry_on_exception(7, base_delay=5, exc_type=_check_ready_retry)
    def check_ready(self):
        """Build a Jenkins client instance."""
        api = Api()
        response = requests.get(api.url)
        if response.status_code >= 500:
            raise ServiceUnavailable()
