class AptStub(object):
    """Testable stub for the charms.apt module from the apt layer.

    @ivar installs: List of packages that have been queued for installation.
    @ivar sources: List of APT sources that have been added.
    """

    def __init__(self):
        self.installs = []
        self.sources = []

    def queue_install(self, packages):
        self.installs.extend(packages)

    def add_source(self, source, key=None):
        self.sources.append((source, key))

    def get_package_version(self, package, full_version=False):
        return '2.150.1'


class AptStubLegacyJenkinsVersion(AptStub):
    """Testable stub that returns an older version of Jenkins"""
    def get_package_version(self, package, full_version=False):
        return '2.128.1'
