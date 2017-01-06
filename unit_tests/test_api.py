from urllib.parse import urljoin
from urllib.error import HTTPError

from jenkins import JenkinsException

from testing import JenkinsTest
from states import JenkinsConfiguredAdmin

from charms.layer.jenkins.service import URL
from charms.layer.jenkins.api import (
    GET_TOKEN_SCRIPT,
    UPDATE_PASSWORD_SCRIPT,
    Api,
)


class ApiTest(JenkinsTest):

    def setUp(self):
        super(ApiTest, self).setUp()
        self.useFixture(JenkinsConfiguredAdmin(self.fakes))
        self.fakes.jenkins.scripts[GET_TOKEN_SCRIPT.format("admin")] = "abc\n"
        self.api = Api()

    def test_wait_transient_failure(self):
        """
        Wait for Jenkins to be fully up, even in spite of transient failures.
        """
        get_whoami = self.fakes.jenkins.get_whoami
        tries = []

        def transient_failure():
            try:
                if not tries:
                    raise JenkinsException("error")
                get_whoami()
            finally:
                tries.append(True)

        self.fakes.jenkins.get_whoami = transient_failure
        self.assertIsNone(self.api.wait())

    def test_update_password(self):
        """
        The update_password() method runs a groovy script to update the
        password for the given user.
        """
        username = "joe"
        password = "new"
        script = UPDATE_PASSWORD_SCRIPT.format(
            username=username, password=password)
        self.fakes.jenkins.scripts[script] = ""
        self.assertIsNone(self.api.update_password(username, password))

    def test_version(self):
        """The version() method returns the version of the Jenkins server."""
        self.assertEqual("2.0.0", self.api.version())

    def test_add(self):
        """
        A slave node can be added by specifying executors and labels.
        """
        self.api.add_node("slave-0", 1, labels=["python"])
        [node] = self.fakes.jenkins.nodes
        self.assertEqual("slave-0", node.host)
        self.assertEqual(1, node.executors)
        self.assertEqual("slave-0", node.description)
        self.assertEqual(["python"], node.labels)
        self.assertEqual("hudson.slaves.JNLPLauncher", node.launcher)

    def test_add_exists(self):
        """
        If a node already exists, nothing is done.
        """
        self.fakes.jenkins.create_node("slave-0", 1, "slave-0")
        self.api.add_node("slave-0", 1, labels=["python"])
        self.assertEqual(1, len(self.fakes.jenkins.nodes))

    def test_add_transient_failure(self):
        """
        Transient failures get retried.
        """
        create_node = self.fakes.jenkins.create_node
        tries = []

        def transient_failure(*args, **kwargs):
            try:
                if not tries:
                    raise JenkinsException("error")
                create_node(*args, **kwargs)
            finally:
                tries.append(True)

        self.fakes.jenkins.create_node = transient_failure
        self.api.add_node("slave-0", 1, labels=["python"])
        self.assertEqual(1, len(self.fakes.jenkins.nodes))

    def test_add_retry_give_up(self):
        """
        If errors persist, we give up.
        """

        def failure(*args, **kwargs):
            raise JenkinsException("error")

        self.fakes.jenkins.create_node = failure
        self.assertRaises(
            JenkinsException, self.api.add_node, "slave-0", 1)

    def test_add_spurious(self):
        """
        If adding a node apparently succeeds, but actually didn't then we
        log an error.
        """
        self.fakes.jenkins.create_node = lambda *args, **kwargs: None
        self.api.add_node("slave-0", 1, labels=["python"])
        self.assertEqual(
            "ERROR: Failed to create node 'slave-0'", self.fakes.juju.log[-1])

    def test_deleted(self):
        """
        A slave node can be deleted by specifyng its host name.
        """
        self.api.add_node("slave-0", 1, labels=["python"])
        self.api.delete_node("slave-0")
        self.assertEqual([], self.fakes.jenkins.nodes)

    def test_deleted_no_present(self):
        """
        If a slave node doesn't exists, deleting it is a no-op.
        """
        self.api.delete_node("slave-0")
        self.assertEqual([], self.fakes.jenkins.nodes)

    def test_reload(self):
        """
        The reload method POSTs a request to the '/reload' URL, expecting
        a 503 on the homepage (which happens after redirection).
        """
        error = HTTPError(URL, 503, "Service Unavailable", {}, None)
        error.url = URL
        self.fakes.jenkins.responses[urljoin(URL, "/reload")] = error
        self.api.reload()

    def test_reload_unexpected_error(self):
        """
        If the error code is not 403, the error is propagated.
        """
        error = HTTPError(URL, 403, "Forbidden", {}, None)
        self.fakes.jenkins.responses[urljoin(URL, "/reload")] = error
        self.assertRaises(HTTPError, self.api.reload)

    def test_reload_unexpected_url(self):
        """
        If the error URL is not the root, the error is propagated.
        """
        error = HTTPError(URL, 503, "Service Unavailable", {}, None)
        error.url = "/foo"
        self.fakes.jenkins.responses[urljoin(URL, "/reload")] = error
        self.assertRaises(HTTPError, self.api.reload)

    def test_reload_unexpected_success(self):
        """
        If the request unexpectedly succeeds, an error is raised.
        """
        self.fakes.jenkins.responses[urljoin(URL, "/reload")] = "home"
        self.assertRaises(RuntimeError, self.api.reload)
