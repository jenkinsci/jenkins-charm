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
    when_any,
    only_once,
    set_state,
    remove_state,
)
from charms.reactive.bus import get_state
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
from charms.layer.jenkins.api import Api

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
@when_not("apt.installed.jenkins")
@when(*DEPENDENCIES_EVENTS)
def install_jenkins():
    status_set("maintenance", "Installing Jenkins")
    packages = Packages()
    packages.install_jenkins()


# Called once the jenkins package has been installed, but we didn't
# perform any configuration yet. We'll not touch config.xml ever again,
# since from this point it should be managed by the user (or by some
# subordinate charm via the 'jenkins-extension' interface).
@only_once()
@when("apt.installed.jenkins")
def bootstrap_jenkins():
    status_set("maintenance", "Bootstrapping Jenkins configuration")
    configuration = Configuration()
    configuration.bootstrap()
    set_state("jenkins.bootstrapped")


# Called once we're bootstrapped and every time the configured tools
# change.
@when("jenkins.bootstrapped", "config.changed.tools")
def configure_tools():
    remove_state("jenkins.configured.tools")
    status_set("maintenance", "Installing tools")
    packages = Packages()
    packages.install_tools()
    set_state("jenkins.configured.tools")


# Called once we're bootstrapped and every time the configured user
# changes.
@when("jenkins.bootstrapped")
@when_any("config.changed.username", "config.changed.password")
def configure_admin():
    remove_state("jenkins.configured.admin")
    status_set("maintenance", "Configuring admin user")
    users = Users()
    users.configure_admin()
    api = Api()
    api.reload()
    api.wait()  # Wait for the service to be fully up
    set_state("jenkins.configured.admin")


# Called once we're bootstrapped and every time the configured plugins
# change.
@when("jenkins.configured.admin", "config.changed.plugins")
def configure_plugins():
    if get_state("extension.connected"):
        # We've been driven by an extension, let it take control over
        # plugin.
        log("External relation detected - skip configuring plugins")
        return
    status_set("maintenance", "Configuring plugins")
    remove_state("jenkins.configured.plugins")
    plugins = Plugins()
    plugins.install(config("plugins"))
    api = Api()
    api.wait()  # Wait for the service to be fully up
    set_state("jenkins.configured.plugins")


@when("jenkins.configured.tools",
      "jenkins.configured.admin",
      "jenkins.configured.plugins")
def ready():
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
    api = Api()
    for slave in slaves:
        api.add_node(
            slave["slavehost"], slave["executors"],
            labels=slave["labels"] or ())


@when("upgrade-charm")
def migrate_charm_data():
    configuration = Configuration()
    configuration.migrate()


@when("stop")
def stop():
    service_stop("jenkins")
    status_set("maintenance", "Jenkins stopped")
