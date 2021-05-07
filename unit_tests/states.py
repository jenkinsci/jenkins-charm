"""Fixtures setting up various reactive state the unit migth be in."""
import os

from fixtures import Fixture

from charmhelpers.core import hookenv

from charms.layer.jenkins import paths
from charms.layer.jenkins.api import Api

INITIAL_PASSWORD = "initial-pw"
GENERATED_PASSWORD = "generated-pw"


class State(Fixture):

    def __init__(self, fakes):
        self.fakes = fakes


class AptInstalledJenkins(State):
    """The jenkins package has been installed."""

    def _setUp(self):
        self.fakes.users.add("jenkins", 123)
        self.fakes.groups.add("nogroup", 456)

        self.fakes.fs.add(paths.HOME)
        os.makedirs(paths.SECRETS)
        with open(paths.INITIAL_PASSWORD, "w") as fd:
            fd.write(INITIAL_PASSWORD)

        self.fakes.fs.add(paths.DEFAULTS_CONFIG_FILE)
        os.makedirs('/etc/default')
        with open(paths.DEFAULTS_CONFIG_FILE, "wb") as fd:
            fd.write(b"# port for HTTP connector\nHTTP_PORT=8080\n")
            fd.write(b'JENKINS_ARGS="--httpPort=$HTTP_PORT"')

        api = Api()
        self.fakes.network.get(api.url, headers={"X-Jenkins": "2.0.0"})


class JenkinsConfiguredAdmin(State):
    """The admin user has been configured."""

    def _setUp(self):
        self.useFixture(AptInstalledJenkins(self.fakes))

        password = hookenv.config()["password"]
        if not password:
            password = GENERATED_PASSWORD
        with open(paths.ADMIN_PASSWORD, "w") as fd:
            fd.write(password)
