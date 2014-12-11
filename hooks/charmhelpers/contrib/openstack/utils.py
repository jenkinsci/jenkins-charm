#!/usr/bin/python

# Common python helper functions used for OpenStack charms.
from collections import OrderedDict
from functools import wraps

import subprocess
import json
import os
import socket
import sys

import six
import yaml

from charmhelpers.core.hookenv import (
    config,
    log as juju_log,
    charm_dir,
    INFO,
    relation_ids,
    relation_set
)

from charmhelpers.contrib.storage.linux.lvm import (
    deactivate_lvm_volume_group,
    is_lvm_physical_volume,
    remove_lvm_physical_volume,
)

from charmhelpers.contrib.network.ip import (
    get_ipv6_addr
)

from charmhelpers.core.host import lsb_release, mounts, umount
from charmhelpers.fetch import apt_install, apt_cache, install_remote
from charmhelpers.contrib.python.packages import pip_install
from charmhelpers.contrib.storage.linux.utils import is_block_device, zap_disk
from charmhelpers.contrib.storage.linux.loopback import ensure_loopback_device

CLOUD_ARCHIVE_URL = "http://ubuntu-cloud.archive.canonical.com/ubuntu"
CLOUD_ARCHIVE_KEY_ID = '5EDB1B62EC4926EA'

DISTRO_PROPOSED = ('deb http://archive.ubuntu.com/ubuntu/ %s-proposed '
                   'restricted main multiverse universe')


UBUNTU_OPENSTACK_RELEASE = OrderedDict([
    ('oneiric', 'diablo'),
    ('precise', 'essex'),
    ('quantal', 'folsom'),
    ('raring', 'grizzly'),
    ('saucy', 'havana'),
    ('trusty', 'icehouse'),
    ('utopic', 'juno'),
])


OPENSTACK_CODENAMES = OrderedDict([
    ('2011.2', 'diablo'),
    ('2012.1', 'essex'),
    ('2012.2', 'folsom'),
    ('2013.1', 'grizzly'),
    ('2013.2', 'havana'),
    ('2014.1', 'icehouse'),
    ('2014.2', 'juno'),
])

# The ugly duckling
SWIFT_CODENAMES = OrderedDict([
    ('1.4.3', 'diablo'),
    ('1.4.8', 'essex'),
    ('1.7.4', 'folsom'),
    ('1.8.0', 'grizzly'),
    ('1.7.7', 'grizzly'),
    ('1.7.6', 'grizzly'),
    ('1.10.0', 'havana'),
    ('1.9.1', 'havana'),
    ('1.9.0', 'havana'),
    ('1.13.1', 'icehouse'),
    ('1.13.0', 'icehouse'),
    ('1.12.0', 'icehouse'),
    ('1.11.0', 'icehouse'),
    ('2.0.0', 'juno'),
    ('2.1.0', 'juno'),
    ('2.2.0', 'juno'),
])

DEFAULT_LOOPBACK_SIZE = '5G'


def error_out(msg):
    juju_log("FATAL ERROR: %s" % msg, level='ERROR')
    sys.exit(1)


def get_os_codename_install_source(src):
    '''Derive OpenStack release codename from a given installation source.'''
    ubuntu_rel = lsb_release()['DISTRIB_CODENAME']
    rel = ''
    if src is None:
        return rel
    if src in ['distro', 'distro-proposed']:
        try:
            rel = UBUNTU_OPENSTACK_RELEASE[ubuntu_rel]
        except KeyError:
            e = 'Could not derive openstack release for '\
                'this Ubuntu release: %s' % ubuntu_rel
            error_out(e)
        return rel

    if src.startswith('cloud:'):
        ca_rel = src.split(':')[1]
        ca_rel = ca_rel.split('%s-' % ubuntu_rel)[1].split('/')[0]
        return ca_rel

    # Best guess match based on deb string provided
    if src.startswith('deb') or src.startswith('ppa'):
        for k, v in six.iteritems(OPENSTACK_CODENAMES):
            if v in src:
                return v


def get_os_version_install_source(src):
    codename = get_os_codename_install_source(src)
    return get_os_version_codename(codename)


def get_os_codename_version(vers):
    '''Determine OpenStack codename from version number.'''
    try:
        return OPENSTACK_CODENAMES[vers]
    except KeyError:
        e = 'Could not determine OpenStack codename for version %s' % vers
        error_out(e)


def get_os_version_codename(codename):
    '''Determine OpenStack version number from codename.'''
    for k, v in six.iteritems(OPENSTACK_CODENAMES):
        if v == codename:
            return k
    e = 'Could not derive OpenStack version for '\
        'codename: %s' % codename
    error_out(e)


def get_os_codename_package(package, fatal=True):
    '''Derive OpenStack release codename from an installed package.'''
    import apt_pkg as apt

    cache = apt_cache()

    try:
        pkg = cache[package]
    except:
        if not fatal:
            return None
        # the package is unknown to the current apt cache.
        e = 'Could not determine version of package with no installation '\
            'candidate: %s' % package
        error_out(e)

    if not pkg.current_ver:
        if not fatal:
            return None
        # package is known, but no version is currently installed.
        e = 'Could not determine version of uninstalled package: %s' % package
        error_out(e)

    vers = apt.upstream_version(pkg.current_ver.ver_str)

    try:
        if 'swift' in pkg.name:
            swift_vers = vers[:5]
            if swift_vers not in SWIFT_CODENAMES:
                # Deal with 1.10.0 upward
                swift_vers = vers[:6]
            return SWIFT_CODENAMES[swift_vers]
        else:
            vers = vers[:6]
            return OPENSTACK_CODENAMES[vers]
    except KeyError:
        e = 'Could not determine OpenStack codename for version %s' % vers
        error_out(e)


def get_os_version_package(pkg, fatal=True):
    '''Derive OpenStack version number from an installed package.'''
    codename = get_os_codename_package(pkg, fatal=fatal)

    if not codename:
        return None

    if 'swift' in pkg:
        vers_map = SWIFT_CODENAMES
    else:
        vers_map = OPENSTACK_CODENAMES

    for version, cname in six.iteritems(vers_map):
        if cname == codename:
            return version
    # e = "Could not determine OpenStack version for package: %s" % pkg
    # error_out(e)


os_rel = None


def os_release(package, base='essex'):
    '''
    Returns OpenStack release codename from a cached global.
    If the codename can not be determined from either an installed package or
    the installation source, the earliest release supported by the charm should
    be returned.
    '''
    global os_rel
    if os_rel:
        return os_rel
    os_rel = (get_os_codename_package(package, fatal=False) or
              get_os_codename_install_source(config('openstack-origin')) or
              base)
    return os_rel


def import_key(keyid):
    cmd = "apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 " \
          "--recv-keys %s" % keyid
    try:
        subprocess.check_call(cmd.split(' '))
    except subprocess.CalledProcessError:
        error_out("Error importing repo key %s" % keyid)


def configure_installation_source(rel):
    '''Configure apt installation source.'''
    if rel == 'distro':
        return
    elif rel == 'distro-proposed':
        ubuntu_rel = lsb_release()['DISTRIB_CODENAME']
        with open('/etc/apt/sources.list.d/juju_deb.list', 'w') as f:
            f.write(DISTRO_PROPOSED % ubuntu_rel)
    elif rel[:4] == "ppa:":
        src = rel
        subprocess.check_call(["add-apt-repository", "-y", src])
    elif rel[:3] == "deb":
        l = len(rel.split('|'))
        if l == 2:
            src, key = rel.split('|')
            juju_log("Importing PPA key from keyserver for %s" % src)
            import_key(key)
        elif l == 1:
            src = rel
        with open('/etc/apt/sources.list.d/juju_deb.list', 'w') as f:
            f.write(src)
    elif rel[:6] == 'cloud:':
        ubuntu_rel = lsb_release()['DISTRIB_CODENAME']
        rel = rel.split(':')[1]
        u_rel = rel.split('-')[0]
        ca_rel = rel.split('-')[1]

        if u_rel != ubuntu_rel:
            e = 'Cannot install from Cloud Archive pocket %s on this Ubuntu '\
                'version (%s)' % (ca_rel, ubuntu_rel)
            error_out(e)

        if 'staging' in ca_rel:
            # staging is just a regular PPA.
            os_rel = ca_rel.split('/')[0]
            ppa = 'ppa:ubuntu-cloud-archive/%s-staging' % os_rel
            cmd = 'add-apt-repository -y %s' % ppa
            subprocess.check_call(cmd.split(' '))
            return

        # map charm config options to actual archive pockets.
        pockets = {
            'folsom': 'precise-updates/folsom',
            'folsom/updates': 'precise-updates/folsom',
            'folsom/proposed': 'precise-proposed/folsom',
            'grizzly': 'precise-updates/grizzly',
            'grizzly/updates': 'precise-updates/grizzly',
            'grizzly/proposed': 'precise-proposed/grizzly',
            'havana': 'precise-updates/havana',
            'havana/updates': 'precise-updates/havana',
            'havana/proposed': 'precise-proposed/havana',
            'icehouse': 'precise-updates/icehouse',
            'icehouse/updates': 'precise-updates/icehouse',
            'icehouse/proposed': 'precise-proposed/icehouse',
            'juno': 'trusty-updates/juno',
            'juno/updates': 'trusty-updates/juno',
            'juno/proposed': 'trusty-proposed/juno',
        }

        try:
            pocket = pockets[ca_rel]
        except KeyError:
            e = 'Invalid Cloud Archive release specified: %s' % rel
            error_out(e)

        src = "deb %s %s main" % (CLOUD_ARCHIVE_URL, pocket)
        apt_install('ubuntu-cloud-keyring', fatal=True)

        with open('/etc/apt/sources.list.d/cloud-archive.list', 'w') as f:
            f.write(src)
    else:
        error_out("Invalid openstack-release specified: %s" % rel)


def save_script_rc(script_path="scripts/scriptrc", **env_vars):
    """
    Write an rc file in the charm-delivered directory containing
    exported environment variables provided by env_vars. Any charm scripts run
    outside the juju hook environment can source this scriptrc to obtain
    updated config information necessary to perform health checks or
    service changes.
    """
    juju_rc_path = "%s/%s" % (charm_dir(), script_path)
    if not os.path.exists(os.path.dirname(juju_rc_path)):
        os.mkdir(os.path.dirname(juju_rc_path))
    with open(juju_rc_path, 'wb') as rc_script:
        rc_script.write(
            "#!/bin/bash\n")
        [rc_script.write('export %s=%s\n' % (u, p))
         for u, p in six.iteritems(env_vars) if u != "script_path"]


def openstack_upgrade_available(package):
    """
    Determines if an OpenStack upgrade is available from installation
    source, based on version of installed package.

    :param package: str: Name of installed package.

    :returns: bool:    : Returns True if configured installation source offers
                         a newer version of package.

    """

    import apt_pkg as apt
    src = config('openstack-origin')
    cur_vers = get_os_version_package(package)
    available_vers = get_os_version_install_source(src)
    apt.init()
    return apt.version_compare(available_vers, cur_vers) == 1


def ensure_block_device(block_device):
    '''
    Confirm block_device, create as loopback if necessary.

    :param block_device: str: Full path of block device to ensure.

    :returns: str: Full path of ensured block device.
    '''
    _none = ['None', 'none', None]
    if (block_device in _none):
        error_out('prepare_storage(): Missing required input: block_device=%s.'
                  % block_device)

    if block_device.startswith('/dev/'):
        bdev = block_device
    elif block_device.startswith('/'):
        _bd = block_device.split('|')
        if len(_bd) == 2:
            bdev, size = _bd
        else:
            bdev = block_device
            size = DEFAULT_LOOPBACK_SIZE
        bdev = ensure_loopback_device(bdev, size)
    else:
        bdev = '/dev/%s' % block_device

    if not is_block_device(bdev):
        error_out('Failed to locate valid block device at %s' % bdev)

    return bdev


def clean_storage(block_device):
    '''
    Ensures a block device is clean.  That is:
        - unmounted
        - any lvm volume groups are deactivated
        - any lvm physical device signatures removed
        - partition table wiped

    :param block_device: str: Full path to block device to clean.
    '''
    for mp, d in mounts():
        if d == block_device:
            juju_log('clean_storage(): %s is mounted @ %s, unmounting.' %
                     (d, mp), level=INFO)
            umount(mp, persist=True)

    if is_lvm_physical_volume(block_device):
        deactivate_lvm_volume_group(block_device)
        remove_lvm_physical_volume(block_device)
    else:
        zap_disk(block_device)


def is_ip(address):
    """
    Returns True if address is a valid IP address.
    """
    try:
        # Test to see if already an IPv4 address
        socket.inet_aton(address)
        return True
    except socket.error:
        return False


def ns_query(address):
    try:
        import dns.resolver
    except ImportError:
        apt_install('python-dnspython')
        import dns.resolver

    if isinstance(address, dns.name.Name):
        rtype = 'PTR'
    elif isinstance(address, six.string_types):
        rtype = 'A'
    else:
        return None

    answers = dns.resolver.query(address, rtype)
    if answers:
        return str(answers[0])
    return None


def get_host_ip(hostname):
    """
    Resolves the IP for a given hostname, or returns
    the input if it is already an IP.
    """
    if is_ip(hostname):
        return hostname

    return ns_query(hostname)


def get_hostname(address, fqdn=True):
    """
    Resolves hostname for given IP, or returns the input
    if it is already a hostname.
    """
    if is_ip(address):
        try:
            import dns.reversename
        except ImportError:
            apt_install('python-dnspython')
            import dns.reversename

        rev = dns.reversename.from_address(address)
        result = ns_query(rev)
        if not result:
            return None
    else:
        result = address

    if fqdn:
        # strip trailing .
        if result.endswith('.'):
            return result[:-1]
        else:
            return result
    else:
        return result.split('.')[0]


def get_matchmaker_map(mm_file='/etc/oslo/matchmaker_ring.json'):
    mm_map = {}
    if os.path.isfile(mm_file):
        with open(mm_file, 'r') as f:
            mm_map = json.load(f)
    return mm_map


def sync_db_with_multi_ipv6_addresses(database, database_user,
                                      relation_prefix=None):
    hosts = get_ipv6_addr(dynamic_only=False)

    kwargs = {'database': database,
              'username': database_user,
              'hostname': json.dumps(hosts)}

    if relation_prefix:
        for key in list(kwargs.keys()):
            kwargs["%s_%s" % (relation_prefix, key)] = kwargs[key]
            del kwargs[key]

    for rid in relation_ids('shared-db'):
        relation_set(relation_id=rid, **kwargs)


def os_requires_version(ostack_release, pkg):
    """
    Decorator for hook to specify minimum supported release
    """
    def wrap(f):
        @wraps(f)
        def wrapped_f(*args):
            if os_release(pkg) < ostack_release:
                raise Exception("This hook is not supported on releases"
                                " before %s" % ostack_release)
            f(*args)
        return wrapped_f
    return wrap


def git_install_requested():
    """Returns true if openstack-origin-git is specified."""
    return config('openstack-origin-git') != "None"


requirements_dir = None


def git_clone_and_install(file_name, core_project):
    """Clone/install all OpenStack repos specified in yaml config file."""
    global requirements_dir

    if file_name == "None":
        return

    yaml_file = os.path.join(charm_dir(), file_name)

    # clone/install the requirements project first
    installed = _git_clone_and_install_subset(yaml_file,
                                              whitelist=['requirements'])
    if 'requirements' not in installed:
        error_out('requirements git repository must be specified')

    # clone/install all other projects except requirements and the core project
    blacklist = ['requirements', core_project]
    _git_clone_and_install_subset(yaml_file, blacklist=blacklist,
                                  update_requirements=True)

    # clone/install the core project
    whitelist = [core_project]
    installed = _git_clone_and_install_subset(yaml_file, whitelist=whitelist,
                                              update_requirements=True)
    if core_project not in installed:
        error_out('{} git repository must be specified'.format(core_project))


def _git_clone_and_install_subset(yaml_file, whitelist=[], blacklist=[],
                                  update_requirements=False):
    """Clone/install subset of OpenStack repos specified in yaml config file."""
    global requirements_dir
    installed = []

    with open(yaml_file, 'r') as fd:
        projects = yaml.load(fd)
        for proj, val in projects.items():
            # The project subset is chosen based on the following 3 rules:
            # 1) If project is in blacklist, we don't clone/install it, period.
            # 2) If whitelist is empty, we clone/install everything else.
            # 3) If whitelist is not empty, we clone/install everything in the
            #    whitelist.
            if proj in blacklist:
                continue
            if whitelist and proj not in whitelist:
                continue
            repo = val['repository']
            branch = val['branch']
            repo_dir = _git_clone_and_install_single(repo, branch,
                                                     update_requirements)
            if proj == 'requirements':
                requirements_dir = repo_dir
            installed.append(proj)
    return installed


def _git_clone_and_install_single(repo, branch, update_requirements=False):
    """Clone and install a single git repository."""
    dest_parent_dir = "/mnt/openstack-git/"
    dest_dir = os.path.join(dest_parent_dir, os.path.basename(repo))

    if not os.path.exists(dest_parent_dir):
        juju_log('Host dir not mounted at {}. '
                 'Creating directory there instead.'.format(dest_parent_dir))
        os.mkdir(dest_parent_dir)

    if not os.path.exists(dest_dir):
        juju_log('Cloning git repo: {}, branch: {}'.format(repo, branch))
        repo_dir = install_remote(repo, dest=dest_parent_dir, branch=branch)
    else:
        repo_dir = dest_dir

    if update_requirements:
        if not requirements_dir:
            error_out('requirements repo must be cloned before '
                      'updating from global requirements.')
        _git_update_requirements(repo_dir, requirements_dir)

    juju_log('Installing git repo from dir: {}'.format(repo_dir))
    pip_install(repo_dir)

    return repo_dir


def _git_update_requirements(package_dir, reqs_dir):
    """Update from global requirements.

       Update an OpenStack git directory's requirements.txt and
       test-requirements.txt from global-requirements.txt."""
    orig_dir = os.getcwd()
    os.chdir(reqs_dir)
    cmd = "python update.py {}".format(package_dir)
    try:
        subprocess.check_call(cmd.split(' '))
    except subprocess.CalledProcessError:
        package = os.path.basename(package_dir)
        error_out("Error updating {} from global-requirements.txt".format(package))
    os.chdir(orig_dir)
