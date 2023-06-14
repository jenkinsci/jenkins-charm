from unittest import mock
from urllib.parse import urljoin

from charmhelpers.core import hookenv
from charms.layer.jenkins.api import (
    CONFIGURE_PROXY_NO_PROXY_WITH_AUTH_SCRIPT,
    CONFIGURE_PROXY_WITH_AUTH_SCRIPT,
    CONFIGURE_PROXY_WITHOUT_AUTH_SCRIPT,
    DISABLE_PROXY_SCRIPT,
    GET_LEGACY_TOKEN_SCRIPT,
    GET_NEW_TOKEN_SCRIPT,
    SET_UPDATE_CENTER_SCRIPT,
    UPDATE_PASSWORD_SCRIPT,
    Api,
)
from charms.layer.jenkins.packages import Packages
from jenkins import JenkinsException
from requests import Request, Response
from requests.exceptions import HTTPError
from states import JenkinsConfiguredAdmin
from stubs.apt import AptStub
from testing import JenkinsTest


class ApiTest(JenkinsTest):
    def setUp(self):
        super(ApiTest, self).setUp()
        self.useFixture(JenkinsConfiguredAdmin(self.fakes))
        self.fakes.jenkins.scripts[GET_LEGACY_TOKEN_SCRIPT.format("admin")] = "abc\n"
        self.fakes.jenkins.scripts[GET_NEW_TOKEN_SCRIPT.format("admin")] = "xyz\n"
        self.apt = AptStub()
        self.packages = Packages(apt=self.apt)
        self.api = Api(packages=self.packages)

    def test_wait_transient_failure(self):
        """
        Wait for Jenkins to be fully up, even in spite of transient failures.
        """
        self.apt._set_jenkins_version("2.120.1")
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
        self.apt._set_jenkins_version("2.120.1")
        username = "joe"
        password = "new"
        script = UPDATE_PASSWORD_SCRIPT.format(username=username, password=password)
        self.fakes.jenkins.scripts[script] = ""
        self.assertIsNone(self.api.update_password(username, password))

    def test_version(self):
        """The version() method returns the version of the Jenkins server."""
        self.apt._set_jenkins_version("2.120.1")
        self.assertEqual("2.0.0", self.api.version())

    def test_new_token_script(self):
        self.apt._set_jenkins_version("2.150.1")
        self.assertEqual("2.0.0", self.api.version())

    def test_regenerate_broken_token(self):
        # When a token is not working a new will will be created
        self.apt._set_jenkins_version("2.120.1")
        get_whoami = self.fakes.jenkins.get_whoami
        tries = []

        def auth_failure():
            try:
                if not tries:
                    raise JenkinsException("[401]")
                get_whoami()
            finally:
                tries.append(True)

        self.fakes.jenkins.get_whoami = auth_failure
        self.assertIsNone(self.api.wait())

    def test_add(self):
        """
        A slave node can be added by specifying executors and labels.
        """
        self.apt._set_jenkins_version("2.120.1")
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
        self.apt._set_jenkins_version("2.120.1")
        self.fakes.jenkins.create_node("slave-0", 1, "slave-0")
        self.api.add_node("slave-0", 1, labels=["python"])
        self.assertEqual(1, len(self.fakes.jenkins.nodes))

    def test_add_transient_failure(self):
        """
        Transient failures get retried.
        """
        self.apt._set_jenkins_version("2.120.1")
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
        self.apt._set_jenkins_version("2.120.1")

        def failure(*args, **kwargs):
            raise JenkinsException("error")

        self.fakes.jenkins.create_node = failure
        self.assertRaises(JenkinsException, self.api.add_node, "slave-0", 1)

    def test_add_spurious(self):
        """
        If adding a node apparently succeeds, but actually didn't then we
        log an error.
        """
        self.apt._set_jenkins_version("2.120.1")
        self.fakes.jenkins.create_node = lambda *args, **kwargs: None
        self.api.add_node("slave-0", 1, labels=["python"])
        self.assertEqual("ERROR: Failed to create node 'slave-0'", self.fakes.juju.log[-1])

    def test_deleted(self):
        """
        A slave node can be deleted by specifyng its host name.
        """
        self.apt._set_jenkins_version("2.120.1")
        self.api.add_node("slave-0", 1, labels=["python"])
        self.api.delete_node("slave-0")
        self.assertEqual([], self.fakes.jenkins.nodes)

    def test_deleted_no_present(self):
        """
        If a slave node doesn't exists, deleting it is a no-op.
        """
        self.apt._set_jenkins_version("2.120.1")
        self.api.delete_node("slave-0")
        self.assertEqual([], self.fakes.jenkins.nodes)

    def _make_httperror(self, url, status_code, reason):
        response = Response()
        response.reason = reason
        response.status_code = status_code
        response.url = url
        return HTTPError(request=Request("POST", url), response=response)

    def test_reload(self):
        """
        The reload method POSTs a request to the '/reload' URL, expecting
        a 503 on the homepage (which happens after redirection).
        """
        self.apt._set_jenkins_version("2.120.1")
        error = self._make_httperror(self.api.url, 503, "Service Unavailable")
        self.fakes.jenkins.responses[urljoin(self.api.url, "reload")] = error
        self.api.reload()

    def test_restart(self):
        # The restart method POSTs a request to the '/safeRestart' URL, expecting
        # a 503 on the homepage (which happens after redirection).
        self.apt._set_jenkins_version("2.120.1")
        error = self._make_httperror(self.api.url, 503, "Service Unavailable")
        self.fakes.jenkins.responses[urljoin(self.api.url, "safeRestart")] = error
        self.api.restart()

    def test_get_plugin_version(self):
        """
        If the plugin is installed it will return its version
        otherwise it will return false.
        """
        self.fakes.jenkins.scripts[
            "println(Jenkins.instance.pluginManager.plugins.find{it.shortName == 'installed-plugin'}?.version)"
        ] = "1"
        self.fakes.jenkins.scripts[
            "println(Jenkins.instance.pluginManager.plugins.find{it.shortName == 'not-installed-plugin'}?.version)"
        ] = "null"
        self.assertEqual(self.api.get_plugin_version("installed-plugin"), "1")
        self.assertFalse(self.api.get_plugin_version("not-installed-plugin"))

    def test_configure_proxy(self):
        """Test proxy configuration."""
        # Firstly without authentication
        hostname = "proxy.example.tld"
        port = 3128
        script = CONFIGURE_PROXY_WITHOUT_AUTH_SCRIPT.format(hostname=hostname, port=port)
        self.fakes.jenkins.scripts[script] = ""
        self.assertIsNone(self.api.configure_proxy(hostname, port))
        # Then with authentication
        username = "admin"
        password = "x"
        script = CONFIGURE_PROXY_WITH_AUTH_SCRIPT.format(
            hostname=hostname, port=port, username=username, password=password
        )
        self.fakes.jenkins.scripts[script] = ""
        self.assertIsNone(self.api.configure_proxy(hostname, port, username, password))
        # Then with no proxy
        no_proxy = "testing.test"
        script = CONFIGURE_PROXY_NO_PROXY_WITH_AUTH_SCRIPT.format(
            hostname=hostname,
            port=port,
            username=username,
            password=password,
            no_proxy_hosts=no_proxy,
        )
        self.fakes.jenkins.scripts[script] = ""
        self.assertIsNone(self.api.configure_proxy(hostname, port, username, password, no_proxy))
        # And finally removal
        script = DISABLE_PROXY_SCRIPT
        self.fakes.jenkins.scripts[script] = ""
        self.assertIsNone(self.api.configure_proxy())

    def test_quiet_down(self):
        """If quiet_down is called it will log to juju logs"""
        self.apt._set_jenkins_version("2.120.1")
        success = Response()
        success.status_code = 200
        self.fakes.jenkins.responses[urljoin(self.api.url, "quietDown")] = success
        self.api.quiet_down()
        self.assertEqual("INFO: Jenkins is in Quiet mode.", self.fakes.juju.log[-1])

    def test_cancel_quiet_down(self):
        """If cancel_quiet_down is called it will log to juju logs"""
        self.apt._set_jenkins_version("2.120.1")
        success = Response()
        success.status_code = 200
        self.fakes.jenkins.responses[urljoin(self.api.url, "cancelQuietDown")] = success
        self.api.cancel_quiet_down()
        self.assertEqual("INFO: Quiet mode has been cancelled", self.fakes.juju.log[-1])

    def test_reload_unexpected_error(self):
        """
        If the error code is not 403, the error is propagated.
        """
        self.apt._set_jenkins_version("2.120.1")
        error = self._make_httperror(self.api.url, 403, "Forbidden")
        self.fakes.jenkins.responses[urljoin(self.api.url, "reload")] = error
        self.assertRaises(HTTPError, self.api.reload)

    def test_reload_unexpected_url(self):
        """
        If the error URL is not the root, the error is propagated.
        """
        self.apt._set_jenkins_version("2.120.1")
        error = self._make_httperror(self.api.url, 503, "Service Unavailable")
        error.response.url = urljoin(self.api.url, "/foo")
        self.fakes.jenkins.responses[urljoin(self.api.url, "reload")] = error
        self.assertRaises(HTTPError, self.api.reload)

    def test_reload_unexpected_success(self):
        """
        If the request unexpectedly succeeds, an error is raised.
        """
        self.apt._set_jenkins_version("2.120.1")
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
            self.assertEqual(self.api.url, "http://localhost:8080/")

            config["public-url"] = "http://here:8080/jenkins"
            self.assertEqual(self.api.url, "http://localhost:8080/jenkins/")
        finally:
            config["public-url"] = orig_public_url

    def test_get_node_secret(self):
        def failure(*args, **kwargs):
            raise JenkinsException("error")

        self.fakes.jenkins.scripts[
            'println(jenkins.model.Jenkins.getInstance().getComputer("jenkins-agent-0").getJnlpMac())'
        ] = "23737cc9d891deaeb117fea094b62ee34cbedfd3478bf2209c97c390f73d48f2"
        self.assertEqual(
            self.api.get_node_secret("jenkins-agent-0"),
            "23737cc9d891deaeb117fea094b62ee34cbedfd3478bf2209c97c390f73d48f2",
        )
        self.fakes.jenkins.run_script = failure
        self.assertFalse(self.api.get_node_secret("jenkins-agent-10"))

    def test_set_update_center(self):
        """
        The set_update_center() method runs a groovy script to modify the
        update center url.
        """
        url = "https://example.jenkins.io/update_center.json"
        script = SET_UPDATE_CENTER_SCRIPT.format(url=url)
        self.fakes.jenkins.scripts[script] = ""
        self.assertIsNone(self.api.set_update_center(url))

    def test_reset_update_center(self):
        """
        The set_update_center() method runs a groovy script to modify the
        update center url to default when no url value is given.
        """
        url = "https://updates.jenkins.io/stable/update-center.json"
        script = SET_UPDATE_CENTER_SCRIPT.format(url=url)
        self.fakes.jenkins.scripts[script] = ""
        self.assertIsNone(self.api.set_update_center())

    def test_check_update_center(self):
        """
        The set_update_center() method runs a groovy script to modify the
        update center url to default when no url value is given.
        """
        script = (
            "Jenkins.instance.getUpdateCenter().getSites().each { site ->"
            "  site.updateDirectlyNow(hudson.model.DownloadService.signatureCheck)"
            "};"
            "hudson.model.DownloadService.Downloadable.all().each { downloadable ->"
            "  downloadable.updateNow();"
            "}"
        )
        self.fakes.jenkins.scripts[script] = ""
        self.assertIsNone(self.api.check_update_center())

    def test_get_updatable_plugins(self):
        """get_updatable_plugins() should return a list of plugins"""
        script = (
            "println(Jenkins.instance.pluginManager.activePlugins.findAll {"
            "  it -> it.hasUpdate()"
            "}.collect {"
            "  it -> it.getShortName()"
            "})"
        )
        self.fakes.jenkins.scripts[script] = "[ plugin1 plugin2 ]"
        self.assertEqual(self.api.get_updatable_plugins(), ["plugin1", "plugin2"])

    def test_update_plugins(self):
        """update_plugins() should return the number of plugins updated"""
        script = (
            "def plugins = Jenkins.instance.pluginManager.activePlugins.findAll {"
            "  it -> it.hasUpdate()"
            "}.collect {"
            "  it -> it.getShortName()"
            "};"
            "long count;"
            "Jenkins.instance.pluginManager.install(plugins, false).each { plugin ->"
            "  ++count"
            "};"
            "println(count)"
        )
        self.fakes.jenkins.scripts[script] = "2"
        self.assertEqual(self.api.update_plugins(), 2)

    @mock.patch("charms.layer.jenkins.api.Api.restart")
    @mock.patch("charms.layer.jenkins.api.Api.update_plugins")
    @mock.patch("charms.layer.jenkins.api.Api.get_updatable_plugins")
    @mock.patch("charms.layer.jenkins.api.Api.check_update_center")
    def test_try_update_plugins(
        self,
        mock_check_update_center,
        mock_get_updatable_plugins,
        mock_update_plugins,
        mock_restart,
    ):
        """try_update_plugins() should return the number of plugins updated"""
        plugins = ["plugin1", "plugin2"]
        mock_get_updatable_plugins.return_value = plugins
        # Test the update
        self.assertEqual(self.api.try_update_plugins(), plugins)
        # Test when there are no plugins to be updated
        mock_get_updatable_plugins.return_value = []
        self.assertEqual(self.api.try_update_plugins(), False)
