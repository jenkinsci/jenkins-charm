from charmhelpers.core.hookenv import Config


class HookenvStub(object):
    """Testable stub for charmhelpers.core.hookenv."""

    def __init__(self, charm_dir):
        self.messages = []
        # We should disable implicit saving since it runs at charm exit using
        # globals :(
        self._config = Config()
        # self._config.implicit_save = False

        self._charm_dir = charm_dir

    def config(self):
        return self._config

    def charm_dir(self):
        return self._charm_dir

    def log(self, message, level=None):
        self.messages.append((message, level))
