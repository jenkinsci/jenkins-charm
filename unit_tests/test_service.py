import time

from charmtest import CharmTest

from charms.layer.jenkins.service import (
    URL,
    ServiceUnavailable,
    Service,
)


class ServiceTest(CharmTest):

    def setUp(self):
        super().setUp()
        self.service = Service()

    def test_check_ready(self):
        """
        If the service is ready, no exception is raised.
        """
        self.fakes.network.get("http://localhost:8080", status_code=403)
        self.assertIsNone(self.service.check_ready())

    def test_check_ready_transient_failure(self):
        """
        Transient failures are retried.
        """
        start = time.time()

        def callback(requests, context):
            if time.time() - start >= 2:
                context.status_code = 503
            else:
                context.status_code = 200
            return ""

        self.fakes.network.get(URL, text=callback)
        self.assertIsNone(self.service.check_ready())

    def test_check_ready_unavailable(self):
        """
        If the backend keeps returning 5xx, an error is raised.
        """
        self.fakes.network.get(URL, status_code=500)
        self.assertRaises(ServiceUnavailable, self.service.check_ready)
