from collections import namedtuple

File = namedtuple("File", ["path", "content", "owner", "group", "perms"])
Dir = namedtuple("Dir", ["path", "owner", "group", "perms"])
Action = namedtuple("Action", ["name", "service"])


class HostStub(object):
    """Testable stub for charmhelpers.core.host."""

    password = "eegh5ahGh5joiph"

    def __init__(self):
        self.files = []
        self.dirs = []
        self.actions = []

    def pwgen(self, length=None):
        if length is None:
            length = len(self.password)
        return self.password[:length]

    def write_file(self, path, content, owner="root", group="root",
                   perms=0o444):
        self.files.append(File(path, content, owner, group, perms))

    def mkdir(self, path, owner="root", group="root", perms=0o555):
        self.dirs.append(Dir(path, owner, group, perms))

    def service_start(self, service_name):
        self.actions.append(Action("start", service_name))

    def service_stop(self, service_name):
        """Stop a system service"""
        self.actions.append(Action("stop", service_name))
