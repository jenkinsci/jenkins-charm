from charms.reactive import (
    when,
    when_not,
)
#    set_state,

from charmhelpers.core import hookenv
from charmhelpers.core.host import (
    service_restart,
    service_start,
    service_stop,
)

from jenkinslib import (
    APT_JENKINS_DEPS,
    JenkinsUnit,
)

APT_INSTALLED_DEPS = ["apt.installed.%s" % dep for dep in APT_JENKINS_DEPS]


def install_deps():
    hookenv.status_set("maintenance", "Installing Jenkins dependencies")
    unit.install_deps()

for event in APT_INSTALLED_DEPS:
    install_deps = when_not(event)(install_deps)


@when(*APT_INSTALLED_DEPS)
@when_not("apt.installed.jenkins")
def install_jenkins():
    hookenv.status_set("maintenance", "Installing Jenkins")
    unit.install_jenkins()
    # set_state("jenkins.installed")


@when("apt.installed.jenkins", "config-changed")
def setup_jenkins():
    hookenv.status_set("maintenance", "Setting up Jenkins")
    unit.configure_admin_user()
    unit.configure_server()
    unit.install_plugins()
    unit.install_tools()


@when("start")
def start():
    service_start("jenkins")


@when("stop")
def stop():
    service_stop("jenkins")


unit = JenkinsUnit()
