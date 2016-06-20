from charms.reactive import when_not, set_state

from charmhelpers.core import hookenv

from jenkinslib import Jenkins


@when_not('jenkins.installed')
def install_jenkins():
    # XXX This is mainly for backward compatibility in case one has a custom
    #     fork of the jenkins charm based on the pre-layers version, and wants
    #     to upgrade the code to this layered version without any change.
    hookenv.status_set("maintenance", 'Installing Jenkins')
    jenkins = Jenkins()
    jenkins.install()
    set_state('jenkins.installed')
