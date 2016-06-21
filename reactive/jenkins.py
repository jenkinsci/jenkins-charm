from charmhelpers.core import hookenv
from charmhelpers.core.host import (
    service_start,
    service_stop,
)

from charms.reactive import (
    when,
    when_not,
    set_state,
)
from charms.layer.execd import execd_preinstall

from packages import APT_DEPENDENCIES, Packages
from configuration import (
    PORT,
    Configuration,
)
from users import Users
from plugins import Plugins

DEPENDENCIES_EVENTS = ["apt.installed.%s" % dep for dep in APT_DEPENDENCIES]


@when("installed")
def exec_install_hooks():
    # XXX This is for backward compatibility, since the pre-layered
    #     version of this charm used a custom exec.d dir, and we want
    #     custom forks of that version to keep working unmodified in
    #     case they merge the code from the new layered charm.
    execd_preinstall("hooks/install.d")


def install_dependencies():
    hookenv.status_set("maintenance", "Installing Jenkins dependencies")
    packages = Packages()
    packages.install_dependencies()

for event in DEPENDENCIES_EVENTS:
    install_dependencies = when_not(event)(install_dependencies)


@when(*DEPENDENCIES_EVENTS)
@when_not("apt.installed.jenkins")
def install_jenkins():
    hookenv.status_set("maintenance", "Installing Jenkins")
    packages = Packages()
    packages.install_jenkins()


@when("apt.installed.jenkins")
@when_not("jenkins.configured")
def configure_jenkins():
    hookenv.status_set("maintenance", "Configuring Jenkins")
    configuration = Configuration()
    configuration.bootstrap()
    set_state("jenkins.configured")


@when("jenkins.configured", "config.changed")
def configure_users_and_plugins():
    hookenv.status_set("maintenance", "Configuring users and plugins")

    users = Users()
    users.configure_admin()

    plugins = Plugins()
    plugins.install_configured_plugins()

    hookenv.status_set("active", "Jenkins is running")


@when("start")
def start():
    service_start("jenkins")


@when("stop")
def stop():
    service_stop("jenkins")


@when("website.available")
def configure_website(website):
    website.configure(port=PORT)
