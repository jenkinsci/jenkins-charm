from urllib.parse import urlparse

from charmhelpers.core import unitdata
from charmhelpers.core.hookenv import (
    log,
    config,
    in_relation_hook,
    relation_id,
    relation_get,
    storage_get,
)
from charmhelpers.core.host import (
    service_restart,
    service_start,
    service_stop,
)

from charms.reactive import (
    hook,
    when,
    when_not,
    when_any,
    set_state,
    remove_state,
)
from charms.reactive.bus import get_state
from charms.reactive.helpers import data_changed
from charms.reactive import RelationBase
from charms.layer.execd import execd_preinstall
from charms.apt import status_set

from charms.layer.jenkins import paths
from charms.layer.jenkins.packages import APT_DEPENDENCIES, Packages
from charms.layer.jenkins.configuration import (
    PORT,
    Configuration,
)
from charms.layer.jenkins.users import Users
from charms.layer.jenkins.plugins import Plugins
from charms.layer.jenkins.api import Api
from charms.layer.jenkins.credentials import Credentials
from charms.layer.jenkins.service import Service
from charms.layer.jenkins.storage import Storage

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


# This is intended for the release=bundle case, but upgrade-charm
# is a good hint that we should upgrade everything possible.
@hook("upgrade-charm")
def upgrade_jenkins():
    status_set("maintenance", "Upgrading Jenkins")
    packages = Packages()
    packages.install_jenkins()


# Called once the jenkins package has been installed, but we didn't
# perform any configuration yet. We'll not touch config.xml ever again,
# since from this point it should be managed by the user (or by some
# subordinate charm via the 'jenkins-extension' interface).
@when_not("jenkins.bootstrapped")
@when("apt.installed.jenkins")
def bootstrap_jenkins():
    status_set("maintenance", "Bootstrapping Jenkins configuration")
    service = Service()
    service.check_ready()
    configuration = Configuration()
    if configuration.bootstrap():
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
@when_any("config.changed.username", "config.changed.password",
          "config.changed.public-url")
def configure_admin():
    remove_state("jenkins.configured.admin")
    api = Api()

    status_set("maintenance", "Configuring Jenkins public url")
    configuration = Configuration()
    needs_restart = configuration.set_url()
    if needs_restart:
        status_set("maintenance", "Restarting Jenkins")
        service_restart('jenkins')
        api.wait()

    status_set("maintenance", "Configuring admin user")
    users = Users()
    users.configure_admin()

    api.reload()
    api.wait()  # Wait for the service to be fully up
    # Inform any extension that the username/password changed
    if get_state("extension.connected"):
        extension_relation = (RelationBase.from_state("extension.connected"))
        extension_relation.joined()

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


@hook('jenkins-storage-attached')
def attach():
    homedir = storage_get()['location']
    set_jenkins_dir(homedir)


@hook('jenkins-storage-detaching')
def detaching():
    # This hook triggers before the stop hook when removing the application
    set_jenkins_dir()


@when("upgrade-charm")
def migrate_charm_data():
    configuration = Configuration()
    configuration.migrate()


@when('nrpe-external-master.available')
def update_nrpe_config(nagios):
    unit_data = unitdata.kv()
    nagios_hostname = unit_data.get('nagios.hostname', None)
    nagios_host_context = unit_data.get('nagios.host_context', None)

    # require the nrpe-external-master relation to provide the host context
    if in_relation_hook() and relation_id().\
            startswith('nrpe-external-master:'):
        rel = relation_get()
        if 'nagios_host_context' in rel:
            nagios_host_context = rel['nagios_host_context']
            unit_data.set('nagios.host_context', nagios_host_context)

            # We have to strip the nagios host context from the nagios hostname
            # since the nagios.add_check will put it back again...
            nagios_hostname = rel['nagios_hostname']
            if nagios_hostname.startswith(nagios_host_context + '-'):
                nagios_hostname = nagios_hostname[len(nagios_host_context +
                                                      '-'):]

            unit_data.set('nagios.hostname', nagios_hostname)

    if not nagios_hostname or not nagios_host_context:
        return
    # The above boilerplate is needed until this issue is fixed:
    #
    # https://github.com/cmars/nrpe-external-master-interface/issues/6

    status_set('maintenance', 'Updating Nagios configs')

    creds = Credentials()
    check = [
        '/usr/lib/nagios/plugins/check_http', '-H', 'localhost', '-p',
        '8080', '-u', urlparse(Api().url).path, '-a',
        "{}:{}".format(creds.username(), creds.token()),
    ]
    nagios.add_check(check,
                     name="check_jenkins_http",
                     description="Verify Jenkins HTTP is up.",
                     context=nagios_host_context,
                     unit=nagios_hostname)

    status_set('active', 'Ready')


@when("stop")
def stop():
    service_stop("jenkins")
    status_set("maintenance", "Jenkins stopped")


def set_jenkins_dir(storage_dir=paths.HOME):
    status_set("maintenance", "Configuring Jenkins storage")
    jenkins_installed = get_state("apt.installed.jenkins")
    if jenkins_installed:
        service_stop('jenkins')

    if storage_dir is paths.HOME:
        log("Setting Jenkins to use local storage")
        Storage().unlink_home()
    else:
        log("Setting Jenkins to use storage at {}".format(storage_dir))
        Storage().link_home(storage_dir)

    if jenkins_installed:
        status_set("maintenance", "Restarting Jenkins")
        service_start('jenkins')
        Service().check_ready()

    if get_state('jenkins.bootstrapped'):
        # JENKINS_HOME just changed trigger bootstrap again
        remove_state("jenkins.bootstrapped")
        bootstrap_jenkins()
    else:
        status_set('active', 'Ready')
