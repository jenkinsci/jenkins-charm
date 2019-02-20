class AptStub(object):
    """Testable stub for the charms.apt module from the apt layer.

    @ivar installs: List of packages that have been queued for installation.
    @ivar sources: List of APT sources that have been added.
    """

    def __init__(self):
        self.installs = []
        self.sources = []
        self._package_versions = {
            'jenkins': '2.150.1',
            }

    def queue_install(self, packages):
        self.installs.extend(packages)

    def add_source(self, source, key=None):
        self.sources.append((source, key))

    def get_package_version(self, package, full_version=False):
        return self._package_versions.get(package, None)

    def _set_jenkins_version(self, jenkins_version):
        self._package_versions['jenkins'] = jenkins_version
