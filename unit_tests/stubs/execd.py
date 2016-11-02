class ExecdStub(object):
    """Testable stub for the charms.layer.execd module from the basic layer."""

    def execd_preinstall(self, execd_dir=None):
        self.preinstall_dir = execd_dir
