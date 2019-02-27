class CharmHelpersCoreHostStub(object):
    """Testable stub for the charmhelpers.core.host module."""

    def __init__(self):
        self._distro_version = 'xenial'

    def lsb_release(self):
        return {'DISTRIB_CODENAME': self._distro_version}

    def _set_distro_version(self, version):
        self._distro_version = version
