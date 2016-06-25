from testtools.testcase import TestCase

from fixtures import (
    EnvironmentVariable,
    TempDir,
    MonkeyPatch,
)

from jenkins import JenkinsException

from stubs.hookenv import HookenvStub
from stubs.jenkins import JenkinsStub

from charms.layer.jenkins.nodes import (
    TOKEN_SCRIPT,
    Nodes,
)


class NodesTest(TestCase):

    def setUp(self):
        super(NodesTest, self).setUp()
        self.charm_dir = self.useFixture(TempDir())
        self.useFixture(EnvironmentVariable("CHARM_DIR", self.charm_dir.path))
        self.hookenv = HookenvStub(self.charm_dir.path)
        self.hookenv.config()["username"] = "admin"
        self.jenkins = JenkinsStub()
        self.jenkins.scripts[TOKEN_SCRIPT.format("admin")] = "abc\n"
        self.nodes = Nodes(hookenv=self.hookenv, jenkins=self.jenkins)

    def test_wait_transient_failure(self):
        """
        Wait for Jenkins to be fully up, even in spite of transient failures.
        """
        self.useFixture(MonkeyPatch("time.sleep", lambda _: None))

        get_whoami = self.jenkins.get_whoami
        tries = []

        def transient_failure():
            try:
                if not tries:
                    raise JenkinsException("error")
                get_whoami()
            finally:
                tries.append(True)

        self.jenkins.get_whoami = transient_failure
        self.hookenv.config()["password"] = "sekret"
        self.assertIsNone(self.nodes.wait())

    def test_add(self):
        """
        A slave node can be added by specifying executors and labels.
        """
        self.hookenv.config()["password"] = "sekret"
        self.nodes.add("slave-0", 1, labels=["python"])
        [node] = self.jenkins.nodes
        self.assertEqual("slave-0", node.host)
        self.assertEqual(2, node.executors)
        self.assertEqual("slave-0", node.description)
        self.assertEqual(["python"], node.labels)

    def test_add_exists(self):
        """
        If a node already exists, nothing is done.
        """
        self.jenkins.create_node("slave-0", 1, "slave-0")
        self.hookenv.config()["password"] = "sekret"
        self.nodes.add("slave-0", 1, labels=["python"])
        self.assertEqual(1, len(self.jenkins.nodes))

    def test_add_transient_failure(self):
        """
        Transient failures get retried.
        """
        self.useFixture(MonkeyPatch("time.sleep", lambda _: None))

        create_node = self.jenkins.create_node
        tries = []

        def transient_failure(*args, **kwargs):
            try:
                if not tries:
                    raise JenkinsException("error")
                create_node(*args, **kwargs)
            finally:
                tries.append(True)

        self.jenkins.create_node = transient_failure
        self.hookenv.config()["password"] = "sekret"
        self.nodes.add("slave-0", 1, labels=["python"])
        self.assertEqual(1, len(self.jenkins.nodes))

    def test_add_retry_give_up(self):
        """
        If errors persist, we give up.
        """
        self.useFixture(MonkeyPatch("time.sleep", lambda _: None))

        def failure(*args, **kwargs):
            raise JenkinsException("error")

        self.jenkins.create_node = failure
        self.hookenv.config()["password"] = "sekret"
        self.assertRaises(
            JenkinsException, self.nodes.add, "slave-0", 1)

    def test_add_spurious(self):
        """
        If adding a node apparently succeeds, but actually didn't then we
        log an error.
        """
        self.jenkins.create_node = lambda *args, **kwargs: None
        self.hookenv.config()["password"] = "sekret"
        self.nodes.add("slave-0", 1, labels=["python"])
        self.assertEqual(
            ("Failed to create node 'slave-0'", "ERROR"),
            self.hookenv.messages[-1])

    def test_deleted(self):
        """
        A slave node can be deleted by specifyng its host name.
        """
        self.hookenv.config()["password"] = "sekret"
        self.nodes.add("slave-0", 1, labels=["python"])
        self.nodes.delete("slave-0")
        self.assertEqual([], self.jenkins.nodes)

    def test_deleted_no_present(self):
        """
        If a slave node doesn't exists, deleting it is a no-op.
        """
        self.hookenv.config()["password"] = "sekret"
        self.nodes.delete("slave-0")
        self.assertEqual([], self.jenkins.nodes)
