#!/usr/bin/python
import glob
import os
import shutil
import subprocess
import tempfile

from charmhelpers.core.hookenv import (
    config,
    log,
    DEBUG,
    INFO,
    WARNING,
)
from charmhelpers.fetch import (
    apt_update,
    add_source,
)

JENKINS_HOME = '/var/lib/jenkins'
TEMPLATES_DIR = 'templates'


def add_node(host, executors, labels, username, password):
    import jenkins

    l_jenkins = jenkins.Jenkins("http://localhost:8080/", username, password)

    if l_jenkins.node_exists(host):
        log("Node exists - not adding")
        return

    log("Adding node '%s' to Jenkins master" % (host), level=INFO)
    l_jenkins.create_node(host, int(executors) * 2, host, labels=labels)

    if not l_jenkins.node_exists(host):
        log("Failed to create node '%s'" % (host), level=WARNING)


def del_node(host, username, password):
    import jenkins

    l_jenkins = jenkins.Jenkins("http://localhost:8080/", username, password)

    if l_jenkins.node_exists(host):
        log("Node '%s' exists" % (host), level=DEBUG)
        l_jenkins.delete_node(host)
    else:
        log("Node '%s' does not exist - not deleting" % (host), level=INFO)


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

    add_source("deb http://pkg.jenkins-ci.org/%s binary/" % (source), key=key)
    apt_update(fatal=True)


def install_jenkins_plugins(uid, gid):
    plugins = config('plugins')
    if plugins:
        plugins = plugins.split()
    else:
        plugins = []

    log("Installing plugins (%s)" % (' '.join(plugins)))
    plugins_dir = os.path.join(JENKINS_HOME, 'plugins')
    if not os.path.isdir(plugins_dir):
        os.makedirs(plugins_dir)

    os.chmod(plugins_dir, 0755)
    os.chown(plugins_dir, uid, gid)

    track_dir = tempfile.mkdtemp(prefix='/tmp/plugins.installed')
    try:
        installed_plugins = glob.glob("%s/*.hpi" % (plugins_dir))
        for plugin in installed_plugins:
            # Create a ref of installed plugin
            with open(os.path.join(track_dir, plugin), 'w'):
                pass

        plugins_site = config('plugins-site')
        for plugin in plugins:
            # NOTE: by default wget verifies certificates as of 1.10.
            if config('plugins-check-certificate') == "no":
                opts = ["--no-check-certificate"]
            else:
                opts = []

            plugin_filename = "%s.hpi" % (plugin)
            url = os.path.join(plugins_site, 'latest/%s' % (plugin_filename))
            plugins_path = os.path.join(plugins_dir, plugin_filename)
            cmd = ['wget'] + opts + ['--timestamping', url, '-O', plugins_path]
            subprocess.check_call(cmd)
            os.chmod(plugins_path, 0744)
            ref = os.path.join(track_dir, plugin_filename)
            if os.path.exists(ref):
                log("Deleting plugin reference '%s'" % (ref), level=INFO)
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
                    ' '.join(installed_plugins), level=INFO)
    finally:
        shutil.rmtree(track_dir)
