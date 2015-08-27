#!/usr/bin/python
import glob
import os
import shutil
import subprocess
import tempfile

from charmhelpers.core.hookenv import (
    charm_dir,
    config,
    log,
    DEBUG,
    INFO,
    WARNING,
)
from charmhelpers.fetch import (
    apt_install,
    apt_update,
    add_source,
)

from charmhelpers.core.decorators import (
    retry_on_exception,
)

JENKINS_HOME = '/var/lib/jenkins'
JENKINS_USERS = os.path.join(JENKINS_HOME, 'users')
JENKINS_PLUGINS = os.path.join(JENKINS_HOME, 'plugins')
TEMPLATES_DIR = 'templates'


def add_node(host, executors, labels, username, password):
    import jenkins

    @retry_on_exception(2, 2, exc_type=jenkins.JenkinsException)
    def _add_node(*args, **kwargs):
        l_jenkins = jenkins.Jenkins("http://localhost:8080/", username,
                                    password)

        if l_jenkins.node_exists(host):
            log("Node exists - not adding", level=DEBUG)
            return

        log("Adding node '%s' to Jenkins master" % (host), level=INFO)
        l_jenkins.create_node(host, int(executors) * 2, host, labels=labels)

        if not l_jenkins.node_exists(host):
            log("Failed to create node '%s'" % (host), level=WARNING)

    return _add_node()


def del_node(host, username, password):
    import jenkins

    l_jenkins = jenkins.Jenkins("http://localhost:8080/", username, password)

    if l_jenkins.node_exists(host):
        log("Node '%s' exists" % (host), level=DEBUG)
        l_jenkins.delete_node(host)
    else:
        log("Node '%s' does not exist - not deleting" % (host), level=INFO)


def install_from_bundle():
    """Install Jenkins from bundled package."""
    # Check bundled package exists.
    bundle_path = os.path.join(charm_dir(), 'files', 'jenkins.deb')
    if not os.path.isfile(bundle_path):
        errmsg = "'%s' doesn't exist. No package bundled." % (bundle_path)
        raise Exception(errmsg)
    log('Installing from bundled Jenkins package: %s' % bundle_path)
    # Install bundle deps.
    apt_install(['daemon', 'adduser', 'psmisc', 'default-jre'], fatal=True)
    # Run dpkg to install bundled deb.
    env = os.environ.copy()
    subprocess.call(['dpkg', '-i', bundle_path], env=env)


def setup_source(release):
    """Install Jenkins archive."""
    log("Configuring source of jenkins as %s" % release, level=INFO)

    # Configure to use upstream archives
    # lts - debian-stable
    # trunk - debian
    if release == 'lts':
        source = "debian-stable"
    elif release == 'trunk':
        source = "debian"
    else:
        errmsg = "Release '%s' configuration not recognised" % (release)
        raise Exception(errmsg)

    # Setup archive to use appropriate jenkins upstream
    key = 'http://pkg.jenkins-ci.org/%s/jenkins-ci.org.key' % source
    target = "%s-%s" % (source, 'jenkins-ci.org.key')
    subprocess.check_call(['wget', '-q', '-O', target, key])
    with open(target, 'r') as fd:
        key = fd.read()

    deb = "deb http://pkg.jenkins-ci.org/%s binary/" % (source)
    sources_file = "/etc/apt/sources.list.d/jenkins.list"

    found = False
    if os.path.exists(sources_file):
        with open(sources_file, 'r') as fd:
            for line in fd:
                if deb in line:
                    found = True
                    break

        if not found:
            with open(sources_file, 'a') as fd:
                fd.write("%s\n" % deb)
    else:
        with open(sources_file, 'w') as fd:
            fd.write("%s\n" % deb)

    if not found:
        # NOTE: don't use add_source for adding source since it adds deb and
        # deb-src entries but pkg.jenkins-ci.org has no deb-src.
        add_source("#dummy-source", key=key)

    apt_update(fatal=True)


def install_jenkins_plugins(jenkins_uid, jenkins_gid):
    plugins = config('plugins')
    if plugins:
        plugins = plugins.split()
    else:
        plugins = []

    log("Installing plugins (%s)" % (' '.join(plugins)), level=DEBUG)
    if not os.path.isdir(JENKINS_PLUGINS):
        os.makedirs(JENKINS_PLUGINS)

    os.chmod(JENKINS_PLUGINS, 0o0755)
    os.chown(JENKINS_PLUGINS, jenkins_uid, jenkins_gid)

    track_dir = tempfile.mkdtemp(prefix='/tmp/plugins.installed')
    try:
        installed_plugins = glob.glob("%s/*.hpi" % (JENKINS_PLUGINS))
        for plugin in installed_plugins:
            # Create a ref of installed plugin
            with open(os.path.join(track_dir, os.path.basename(plugin)),
                      'w'):
                pass

        plugins_site = config('plugins-site')
        log("Fetching plugins from %s" % (plugins_site), level=DEBUG)
        # NOTE: by default wget verifies certificates as of 1.10.
        if config('plugins-check-certificate') == "no":
            opts = ["--no-check-certificate"]
        else:
            opts = []

        for plugin in plugins:
            plugin_filename = "%s.hpi" % (plugin)
            url = os.path.join(plugins_site, 'latest', plugin_filename)
            plugin_path = os.path.join(JENKINS_PLUGINS, plugin_filename)
            if not os.path.isfile(plugin_path):
                log("Installing plugin %s" % (plugin_filename), level=DEBUG)
                cmd = ['wget'] + opts + ['--timestamping', url, '-O',
                                         plugin_path]
                subprocess.check_call(cmd)
                os.chmod(plugin_path, 0744)
                os.chown(plugin_path, jenkins_uid, jenkins_gid)

            else:
                log("Plugin %s already installed" % (plugin_filename),
                    level=DEBUG)

            ref = os.path.join(track_dir, plugin_filename)
            if os.path.exists(ref):
                # Delete ref since plugin is installed.
                os.remove(ref)

        installed_plugins = os.listdir(track_dir)
        if installed_plugins:
            if config('remove-unlisted-plugins') == "yes":
                for plugin in installed_plugins:
                    path = os.path.join(JENKINS_HOME, 'plugins', plugin)
                    if os.path.isfile(path):
                        log("Deleting unlisted plugin '%s'" % (path),
                            level=INFO)
                        os.remove(path)
            else:
                log("Unlisted plugins: (%s) Not removed. Set "
                    "remove-unlisted-plugins to 'yes' to clear them away." %
                    ', '.join(installed_plugins), level=INFO)
    finally:
        # Delete install refs
        shutil.rmtree(track_dir)
