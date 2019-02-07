import mock

from urllib.parse import urljoin
from requests import Request, Response
from requests.exceptions import HTTPError

from jenkins import JenkinsException

from charmhelpers.core import hookenv
from testing import JenkinsTest
from states import JenkinsConfiguredAdmin

from charms.layer.jenkins.api import (
    GET_LEGACY_TOKEN_SCRIPT,
    GET_NEW_TOKEN_SCRIPT,
    UPDATE_PASSWORD_SCRIPT,
    Api,
)


class ApiTest(JenkinsTest):

    def setUp(self):
        super(ApiTest, self).setUp()
        self.useFixture(JenkinsConfiguredAdmin(self.fakes))
        self.fakes.jenkins.scripts[GET_LEGACY_TOKEN_SCRIPT.format("admin")] = "abc\n"
        self.fakes.jenkins.scripts[GET_NEW_TOKEN_SCRIPT.format("admin")] = "xyz\n"
        self.api = Api()

    @mock.patch('charms.layer.jenkins.packages.Packages.jenkins_version')
    def test_wait_transient_failure(self, _jenkins_version):
        """
        Wait for Jenkins to be fully up, even in spite of transient failures.
        """
        _jenkins_version.return_value = '2.120.1'
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

    @mock.patch('charms.layer.jenkins.packages.Packages.jenkins_version')
    def test_update_password(self, _jenkins_version):
        """
        The update_password() method runs a groovy script to update the
        password for the given user.
        """
        _jenkins_version.return_value = '2.120.1'
        username = "joe"
        password = "new"
        script = UPDATE_PASSWORD_SCRIPT.format(
            username=username, password=password)
        self.fakes.jenkins.scripts[script] = ""
        self.assertIsNone(self.api.update_password(username, password))

    @mock.patch('charms.layer.jenkins.packages.Packages.jenkins_version')
    def test_version(self, _jenkins_version):
        """The version() method returns the version of the Jenkins server."""
        _jenkins_version.return_value = '2.120.1'
        self.assertEqual("2.0.0", self.api.version())

    @mock.patch('charms.layer.jenkins.packages.Packages.jenkins_version')
    def test_new_token_script(self, _jenkins_version):
        _jenkins_version.return_value = '2.150.1'
        self.assertEqual("2.0.0", self.api.version())

    @mock.patch('charms.layer.jenkins.packages.Packages.jenkins_version')
    def test_add(self, _jenkins_version):
        """
        A slave node can be added by specifying executors and labels.
        """
        _jenkins_version.return_value = '2.120.1'
        self.api.add_node("slave-0", 1, labels=["python"])
        [node] = self.fakes.jenkins.nodes
        self.assertEqual("slave-0", node.host)
        self.assertEqual(1, node.executors)
        self.assertEqual("slave-0", node.description)
        self.assertEqual(["python"], node.labels)
        self.assertEqual("hudson.slaves.JNLPLauncher", node.launcher)

    @mock.patch('charms.layer.jenkins.packages.Packages.jenkins_version')
    def test_add_exists(self, _jenkins_version):
        """
        If a node already exists, nothing is done.
        """
        _jenkins_version.return_value = '2.120.1'
        self.fakes.jenkins.create_node("slave-0", 1, "slave-0")
        self.api.add_node("slave-0", 1, labels=["python"])
        self.assertEqual(1, len(self.fakes.jenkins.nodes))

    @mock.patch('charms.layer.jenkins.packages.Packages.jenkins_version')
    def test_add_transient_failure(self, _jenkins_version):
        """
        Transient failures get retried.
        """
        _jenkins_version.return_value = '2.120.1'
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

    @mock.patch('charms.layer.jenkins.packages.Packages.jenkins_version')
    def test_add_retry_give_up(self, _jenkins_version):
        """
        If errors persist, we give up.
        """
        _jenkins_version.return_value = '2.120.1'

        def failure(*args, **kwargs):
            raise JenkinsException("error")

        self.fakes.jenkins.create_node = failure
        self.assertRaises(
            JenkinsException, self.api.add_node, "slave-0", 1)

    @mock.patch('charms.layer.jenkins.packages.Packages.jenkins_version')
    def test_add_spurious(self, _jenkins_version):
        """
        If adding a node apparently succeeds, but actually didn't then we
        log an error.
        """
        _jenkins_version.return_value = '2.120.1'
        self.fakes.jenkins.create_node = lambda *args, **kwargs: None
        self.api.add_node("slave-0", 1, labels=["python"])
        self.assertEqual(
            "ERROR: Failed to create node 'slave-0'", self.fakes.juju.log[-1])

    @mock.patch('charms.layer.jenkins.packages.Packages.jenkins_version')
    def test_deleted(self, _jenkins_version):
        """
        A slave node can be deleted by specifyng its host name.
        """
        _jenkins_version.return_value = '2.120.1'
        self.api.add_node("slave-0", 1, labels=["python"])
        self.api.delete_node("slave-0")
        self.assertEqual([], self.fakes.jenkins.nodes)

    @mock.patch('charms.layer.jenkins.packages.Packages.jenkins_version')
    def test_deleted_no_present(self, _jenkins_version):
        """
        If a slave node doesn't exists, deleting it is a no-op.
        """
        _jenkins_version.return_value = '2.120.1'
        self.api.delete_node("slave-0")
        self.assertEqual([], self.fakes.jenkins.nodes)

    def _make_httperror(self, url, status_code, reason):
        response = Response()
        response.reason = reason
        response.status_code = status_code
        response.url = url
        return HTTPError(request=Request('POST', url), response=response)

    @mock.patch('charms.layer.jenkins.packages.Packages.jenkins_version')
    def test_reload(self, _jenkins_version):
        """
        The reload method POSTs a request to the '/reload' URL, expecting
        a 503 on the homepage (which happens after redirection).
        """
        _jenkins_version.return_value = '2.120.1'
        error = self._make_httperror(self.api.url, 503, "Service Unavailable")
        self.fakes.jenkins.responses[urljoin(self.api.url, "reload")] = error
        self.api.reload()

    @mock.patch('charms.layer.jenkins.packages.Packages.jenkins_version')
    def test_reload_unexpected_error(self, _jenkins_version):
        """
        If the error code is not 403, the error is propagated.
        """
        _jenkins_version.return_value = '2.120.1'
        error = self._make_httperror(self.api.url, 403, "Forbidden")
        self.fakes.jenkins.responses[urljoin(self.api.url, "reload")] = error
        self.assertRaises(HTTPError, self.api.reload)

    @mock.patch('charms.layer.jenkins.packages.Packages.jenkins_version')
    def test_reload_unexpected_url(self, _jenkins_version):
        """
        If the error URL is not the root, the error is propagated.
        """
        _jenkins_version.return_value = '2.120.1'
        error = self._make_httperror(self.api.url, 503, "Service Unavailable")
        error.response.url = urljoin(self.api.url, "/foo")
        self.fakes.jenkins.responses[urljoin(self.api.url, "reload")] = error
        self.assertRaises(HTTPError, self.api.reload)

    @mock.patch('charms.layer.jenkins.packages.Packages.jenkins_version')
    def test_reload_unexpected_success(self, _jenkins_version):
        """
        If the request unexpectedly succeeds, an error is raised.
        """
        _jenkins_version.return_value = '2.120.1'
        self.fakes.jenkins.responses[urljoin(self.api.url, "reload")] = "home"
        self.assertRaises(RuntimeError, self.api.reload)

    def test_url(self):
        """
        Verify the url always ends in a / and has the expected prefix
        """
        config = hookenv.config()
        orig_public_url = config["public-url"]
        try:
            config["public-url"] = ""
            self.assertEqual(self.api.url, 'http://localhost:8080/')

            config["public-url"] = "http://here:8080/jenkins"
            self.assertEqual(self.api.url, 'http://localhost:8080/jenkins/')
        finally:
            config["public-url"] = orig_public_url
