import requests
from distutils.version import LooseVersion
from urllib.parse import urljoin, urlparse

import jenkins
from charmhelpers.core import hookenv
from charmhelpers.core.decorators import retry_on_exception
from charmhelpers.core.hookenv import ERROR

from charms.layer.jenkins.credentials import Credentials
from charms.layer.jenkins.packages import Packages

RETRIABLE = (
    requests.exceptions.RequestException,
    jenkins.JenkinsException,
    )

GET_LEGACY_TOKEN_SCRIPT = """
user = hudson.model.User.get('{}')
prop = user.getProperty(jenkins.security.ApiTokenProperty.class)
println(prop.getApiToken())
"""

GET_NEW_TOKEN_SCRIPT = """
user = hudson.model.User.get('{}')
prop = user.getProperty(jenkins.security.ApiTokenProperty.class)
result = prop.tokenStore.generateNewToken("token-created-by-script")
user.save()
println(result.plainValue)
"""

# flake8: noqa
UPDATE_PASSWORD_SCRIPT = """
user = hudson.model.User.get('{username}')
property = hudson.security.HudsonPrivateSecurityRealm.Details.fromPlainPassword('{password}')
user.addProperty(property)
"""


class Api(object):
    """Encapsulate operations on the Jenkins master."""

    @property
    def url(self):
        config = hookenv.config()
        prefix = urlparse(config["public-url"]).path
        if len(prefix) > 0 and prefix[-1] != '/':
            prefix += '/'
        return urljoin("http://localhost:8080/", prefix)

    def wait(self):
        self._make_client()

    def version(self):
        """Return the version."""
        self.wait()
        response = requests.get(self.url)
        return response.headers["X-Jenkins"]

    def update_password(self, username, password):
        """Update the password for the given user.

        If the user doesn't exist, it will be created.
        """
        client = self._make_client()
        client.run_script(UPDATE_PASSWORD_SCRIPT.format(
            username=username, password=password))

    def add_node(self, host, executors, labels=()):
        """Add a slave node with the given host name."""
        self.wait()

        client = self._make_client()

        @retry_on_exception(3, 3, exc_type=RETRIABLE)
        def _add_node():
            if client.node_exists(host):
                hookenv.log("Node exists - not adding")
                return

            hookenv.log("Adding node '%s' to Jenkins master" % host)

            # See the "Launch slave agent headlessly" section of the Jenkins
            # wiki page about distributed builds:
            #
            # https://wiki.jenkins-ci.org/display/JENKINS/Distributed+builds
            launcher = jenkins.LAUNCHER_JNLP

            client.create_node(
                host, int(executors), host, labels=labels, launcher=launcher)

            if not client.node_exists(host):
                hookenv.log(
                    "Failed to create node '%s'" % host, level=ERROR)

        return _add_node()

    def delete_node(self, host):
        """Delete the slave node with the given host name."""
        client = self._make_client()
        if client.node_exists(host):
            hookenv.log("Node '%s' exists" % host)
            client.delete_node(host)
        else:
            hookenv.log("Node '%s' does not exist - not deleting" % host)

    def reload(self):
        """Reload configuration from disk."""
        hookenv.log("Reloading configuration from disk")
        client = self._make_client()
        request = requests.Request("POST", urljoin(self.url, "reload"))
        try:
            client.jenkins_open(request)
        except requests.exceptions.HTTPError as error:
            # We expect a 'Service Unavailable' error code and to be at the
            # home page.
            if error.response.status_code != 503:
                hookenv.log("Unexpected HTTP response code '%d'" % error.response.status_code)
                raise
            if error.response.url != self.url:
                hookenv.log("Unexpected HTTP response url '%s'" % error.response.url)
                raise
        else:
            raise RuntimeError("Couldn't reload configuration")

    # Wait up to 140 seconds for Jenkins to be fully up.
    @retry_on_exception(7, base_delay=5, exc_type=RETRIABLE)
    def _make_client(self):
        """Build a Jenkins client instance."""
        creds = Credentials()
        user = creds.username()
        token = creds.token()

        # TODO: also handle regenerated tokens
        if token is None:
            client = jenkins.Jenkins(self.url, user, creds.password())
            # If we're using Jenkins >= 2.129 we need to request a new token.
            jenkins_version = Packages().jenkins_version()
            if LooseVersion(jenkins_version) >= LooseVersion('2.129'):
                token = client.run_script(GET_LEGACY_NEW_SCRIPT.format(user)).strip()
            else:
                token = client.run_script(GET_LEGACY_TOKEN_SCRIPT.format(user)).strip()
            creds.token(token)

        client = jenkins.Jenkins(self.url, user, token)
        client.get_whoami()
        return client
