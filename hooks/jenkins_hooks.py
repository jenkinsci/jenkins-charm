#!/usr/bin/python
import grp
import os
import pwd
import shutil
import subprocess
import sys

from charmhelpers.core.hookenv import (
    Hooks,
    UnregisteredHookError,
    config,
    remote_unit,
    relation_get,
    relation_set,
    relation_ids,
    unit_get,
    open_port,
    log,
    DEBUG,
    INFO,
)
from charmhelpers.fetch import apt_install
from charmhelpers.core.host import (
    service_start,
    service_stop,
)
from charmhelpers.payload.execd import execd_preinstall
from jenkins_utils import (
    JENKINS_HOME,
    TEMPLATES_DIR,
    add_node,
    del_node,
    setup_source,
    install_jenkins_plugins,
)

hooks = Hooks()


@hooks.hook('install')
def install():
    # Only setup the source if jenkins is not already installed this makes the
    # config 'release' immutable - i.e. you can change source once deployed
    if not os.path.exists(JENKINS_HOME):
        setup_source(config('release'))

    # Re-run whenever called to pickup any updates
    log("Installing/upgrading jenkins...")
    apt_install(['jenkins', 'default-jre-headless', 'pwgen'], fatal=True)

    # Always run - even if config has not changed, its safe
    log("Configuring user for jenkins...")
    # Check to see if password provided
    admin_passwd = config('password')
    if not admin_passwd:
        # Generate a random one for security. User can then override using juju
        # set.
        admin_passwd = subprocess.check_output(['pwgen', '-N1', '15'])

    passwd_file = os.path.join(JENKINS_HOME, '.admin_password')
    with open(passwd_file, 'w+') as fd:
        fd.write(admin_passwd)

    os.chmod(passwd_file, 0600)

    # Generate Salt and Hash Password for Jenkins
    salt = subprocess.check_output(['pwgen', '-N1', '6'])
    data = "%s%s" % (admin_passwd, salt)
    p = subprocess.Popen(['shasum', '-a', '256'], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, stdin=subprocess.PIPE)
    stdout, stderr = p.communicate(input=data)
    rc = p.returncode
    if rc:
        errmsg = ("Failed to create salt password (rc=%s, stderr=%s)" %
                  (rc, stderr))
        raise Exception(errmsg)

    salty_password = "%s:%s" % (salt, stdout.split(' ')[0])

    admin_username = config('username')
    admin_user_home = os.path.join(JENKINS_HOME, 'users', admin_username)
    if not os.path.isdir(admin_user_home):
        os.makedirs(admin_user_home)

    dst = os.path.join(JENKINS_HOME, 'users', admin_username, 'config.xml')
    with open(dst, 'w') as dst_fd:
        with open(os.path.join(TEMPLATES_DIR, 'user-config.xml')) as src_fd:
            lines = src_fd.readline()
            for line in lines:
                kvs = {'__USERNAME__': admin_username,
                       '__PASSWORD__': salty_password}

                for key, val in kvs.iteritems():
                    line.replace(key, val)

                dst_fd.write(line)

    users_path = os.path.join(JENKINS_HOME, 'users')

    jenkins_uid = pwd.getpwnam('jenkins').pw_uid
    nogroup_gid = grp.getgrnam('nogroup').gr_gid
    os.chown(users_path, jenkins_uid, nogroup_gid)

    # Only run on first invocation otherwise we blast
    # any configuration changes made
    jenkins_bootstrap_flag = '/var/lib/jenkins/config.bootstrapped'
    if not os.path.exists(jenkins_bootstrap_flag):
        log("Bootstrapping secure initial configuration in Jenkins...")
        src = os.path.join(TEMPLATES_DIR, 'jenkins-config.xml')
        dst = os.path.join(JENKINS_HOME, 'config.xml')
        shutil.copy(src, dst)
        os.chown(dst, jenkins_uid, nogroup_gid)
        # Touch
        with open(jenkins_bootstrap_flag, 'w'):
            pass

    log("Stopping jenkins for plugin update(s)", level=DEBUG)
    service_stop('jenkins')
    install_jenkins_plugins(jenkins_uid, nogroup_gid)
    log("Starting jenkins to pickup configuration changes", level=DEBUG)
    service_start('jenkins')

    apt_install(['python-jenkins'], fatal=True)
    tools = config('tools')
    if tools:
        apt_install(tools.split(), fatal=True)

    open_port(8080)
    execd_preinstall('hooks/install.d')


@hooks.hook('config-changed')
def config_changed():
    log("Reconfiguring charm by installing hook again.")
    install()


@hooks.hook('start')
def start():
    service_start('jenkins')


@hooks.hook('stop')
def stop():
    service_stop('jenkins')


@hooks.hook('upgrade-charm')
def upgrade_charm():
    log("Upgrading charm by running install hook again.")
    install()


@hooks.hook('master-relation-joined')
def master_relation_joined():
    HOSTNAME = unit_get('private-address')
    log("Setting url relation to http://%s:8080" % (HOSTNAME))
    relation_set(url="http://%s:8080" % (HOSTNAME))


@hooks.hook('master-relation-changed')
def master_relation_changed():
    PASSWORD = config('password')
    if PASSWORD:
        with open('/var/lib/jenkins/.admin_password', 'r') as fd:
            PASSWORD = fd.read()

    # Grab information that remote unit has posted to relation
    slavehost = relation_get('slavehost')
    executors = relation_get('executors')
    labels = relation_get('labels')

    # Double check to see if this has happened yet
    if "x%s" % (slavehost) == "x":
        log("Slave host not yet defined, exiting...")
        return

    log("Adding slave with hostname $slavehost...")
    add_node(slavehost, executors, labels, config('username'), PASSWORD)
    log("Node slave $slavehost added...")


@hooks.hook('master-relation-departed')
def master_relation_departed():
    # Slave hostname is derived from unit name so
    # this is pretty safe
    slavehost = remote_unit()
    log("Deleting slave with hostname $slavehost...")
    del_node(slavehost, config('username'), config('password'))


@hooks.hook('master-relation-broken')
def master_relation_broken():
    PASSWORD = config('password')
    if not "$PASSWORD":
        passwd_file = os.path.join(JENKINS_HOME, '.admin_password')
        with open(passwd_file, 'w+') as fd:
            PASSWORD = fd.read()

    for MEMBER in relation_ids():
        log("Removing node $MEMBER from Jenkins master...")
        del_node(MEMBER.replace('/', '-'), config('username'), PASSWORD)


@hooks.hook('website-relation-joined')
def website_relation_joined():
    HOSTNAME = unit_get('private-address')
    log("Setting website URL to $HOSTNAME:8080")
    relation_set(port=8080, hostname=HOSTNAME)


if __name__ == '__main__':
    try:
        hooks.execute(sys.argv)
    except UnregisteredHookError as e:
        log('Unknown hook {} - skipping.'.format(e), level=INFO)
