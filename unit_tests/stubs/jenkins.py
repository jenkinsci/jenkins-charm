from collections import namedtuple

Node = namedtuple("Node", ["host", "executors", "description", "labels"])


class JenkinsStub(object):
    """Testable stub for the Jenkins python client."""

    def __init__(self):
        self.nodes = []
        self.scripts = {}

    def __call__(self, url, username, password):
        self.url = url
        self.username = username
        self.password = password
        return self

    def get_whoami(self):
        return {"id": "admin"}

    def node_exists(self, host):
        for node in self.nodes:
            if node.host == host:
                return True
        return False

    def create_node(self, host, executors, description, labels=()):
        self.nodes.append(Node(host, executors, description, labels))

    def delete_node(self, host):
        for node in self.nodes[:]:
            if node.host == host:
                self.nodes.remove(node)

    def run_script(self, script):
        return self.scripts[script]
