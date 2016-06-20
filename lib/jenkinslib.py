from charmhelpers.core import hookenv


class Jenkins(object):
    """Charm-level logic for managing a jenkins unit."""

    def __init__(self, execd=None, hookenv=hookenv):
        """
        @param execd: An object implementing the charms.layer.execd API from
            the basic charm layer (for testing).
        @param hookenv: An object implementing the charmhelpers.core.hookenv
            API from charmhelpers (for testing).
        """
        if execd is None:
            from charms.layer import execd
        self._execd = execd
        self._hookenv = hookenv

    def install(self):
        """Install the Jenkins bits."""
        # XXX This is for backward compatibility, since the the pre-layered
        #     version of this charm used a custom exec.d dir, and we want
        #     custom forks of that version to keep working unmodified in
        #     case they merge the code from the new layered charm.
        self._execd.execd_preinstall("hooks/install.d")
