from charmhelpers.core.hookenv import (
    log,
    config,
)
from charmhelpers.core.host import (
    service_stop,
)

from charms.reactive import (
    hook,
    when,
    when_not,
    set_state,
)
from charms.reactive.helpers import data_changed
from charms.layer.execd import execd_preinstall
from charms.apt import status_set

from charms.layer.jenkins.packages import APT_DEPENDENCIES, Packages
from charms.layer.jenkins.configuration import (
    PORT,
    Configuration,
)
from charms.layer.jenkins.users import Users
from charms.layer.jenkins.plugins import Plugins
from charms.layer.jenkins.nodes import Nodes

DEPENDENCIES_EVENTS = ["apt.installed.%s" % dep for dep in APT_DEPENDENCIES]


# XXX This is for backward compatibility, since the pre-layered
#     version of this charm used a custom exec.d dir, and we want
#     custom forks of that version to keep working unmodified in
#     case they merge the code from the new layered charm.
@hook("install")
def exec_install_hooks():
    log("Invoking pre-install hooks under hooks/install.d")
    execd_preinstall("hooks/install.d")


def install_dependencies():
    packages = Packages()
    packages.install_dependencies()

# Dynamically create an OR-ed chain of @when_not, so install_dependencies
# will get triggered whenever one or more dependencies are unmet (typically
# at install time).
for event in DEPENDENCIES_EVENTS:
    install_dependencies = when_not(event)(install_dependencies)


# When all dependencies have been installed, we install the jenkins package
# from the desired source.
@when(*DEPENDENCIES_EVENTS)
@when_not("apt.installed.jenkins")
def install_jenkins():
    status_set("maintenance", "Installing Jenkins")
    packages = Packages()
    packages.install_jenkins()


# Called within the install hook once the jenkins package has been installed,
# but we didn't perform any configuration yet.
@when("apt.installed.jenkins")
@when_not("jenkins.configured")
def configure_jenkins():
    status_set("maintenance", "Configuring Jenkins")
    configuration = Configuration()
    configuration.bootstrap()
    set_state("jenkins.configured")


# Called both within the installed hook after the global configuration has
# been bootstrapped and after any service config changes.
@when("jenkins.configured", "config.changed")
def configure_users_and_plugins():
    status_set("maintenance", "Configuring users and plugins")

    users = Users()
    users.configure_admin()

    plugins = Plugins()
    plugins.install(config("plugins"))

    nodes = Nodes()
    nodes.wait()  # Wait for the service to be fully up

    status_set("active", "Jenkins is running")


@when("website.available")
def configure_website(website):
    website.configure(port=PORT)


@when("master.available")
def add_slaves(master):
    slaves = master.slaves()
    if not data_changed("master.slaves", slaves):
        log("Slaves are unchanged - no need to do anything")
        return
    nodes = Nodes()
    for slave in slaves:
        nodes.add(
            slave["slavehost"], slave["executors"],
            labels=slave["labels"] or ())


@when("upgrade-charm")
def migrate_charm_data():
    configuration = Configuration()
    configuration.migrate()

    users = Users()
    users.migrate()


@when("stop")
def stop():
    service_stop("jenkins")
    status_set("maintenance", "Jenkins stopped")
