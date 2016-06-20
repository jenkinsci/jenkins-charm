from charms.reactive import when, when_not, set_state
from charms.lib.execd import execd_preinstall


@when_not('jenkins.installed')
def install_jenkins():
    # XXX This is mainly for backward compatibility in case one has a custom
    #     fork of the jenkins charm based on the pre-layers version, and wants
    #     to upgrade the code to this layered version without any change.
    execd_preinstall('hooks/install.d')
    set_state('jenkins.installed')
