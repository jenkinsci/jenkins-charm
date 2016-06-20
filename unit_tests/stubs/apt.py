class AptStub(object):
    """Testable stub for the charms.apt module from the apt layer."""

    def __init__(self):
        self.installs = []
        self.sources = []

    def queue_install(self, packages):
        self.installs.extend(packages)

    def add_source(self, source, key=None):
        self.sources.append((source, key))
