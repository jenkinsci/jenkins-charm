import os
import shutil
import glob
import tempfile
import subprocess
import hashlib

from testtools import try_import

from charmhelpers.core import hookenv
from charmhelpers.core import host
from charmhelpers.core import templating
from charmhelpers.core.hookenv import DEBUG

# XXX Wrap these imports with try_import since layers code won't be available
#     when running unit tests for this layer (and in such case import errors
#     can be safely ignored since we're stubbing out these objects).
execd = try_import("charms.layer.execd")
apt = try_import("charms.apt")

APT_JENKINS_DEPS = ["daemon", "default-jre-headless"]
APT_JENKINS_SOURCE = "deb http://pkg.jenkins-ci.org/%s binary/"
APT_JENKINS_KEY = "http://pkg.jenkins-ci.org/%s/jenkins-ci.org.key"

JENKINS_HOME = "/var/lib/jenkins"
JENKINS_USERS = os.path.join(JENKINS_HOME, "users")
JENKINS_PASSWORD_FILE = os.path.join(JENKINS_HOME, ".admin_password")
JENKINS_PLUGINS = os.path.join(JENKINS_HOME, "plugins")
JENKINS_CONFIG_FILE = os.path.join(JENKINS_HOME, "config.xml")

TEMPLATES_DIR = "templates"


class JenkinsUnit(object):
    """Charm-level logic for managing a jenkins unit."""

    def __init__(self, subprocess=subprocess, hookenv=hookenv, host=host,
                 templating=templating, execd=execd, apt=apt):
        """
        @param subprocess: An object implementing the subprocess API (for
            testing).
        @param hookenv: An object implementing the charmhelpers.core.hookenv
            API from charmhelpers (for testing).
        @param host: An object implementing the charmhelpers.core.host API
            from charmhelpers (for testing).
        @param host: An object implementing the charmhelpers.core.templating
            API from charmhelpers (for testing).
        @param host: An object implementing the charmhelpers.fetcher.archiveurl
            API from charmhelpers (for testing).
        @param execd: An object implementing the charms.layer.execd API from
            the basic charm layer (for testing).
        @param apt: An object implementing the charms.apt API from the apt
            charm layer (for testing).
        """
        self._subprocess = subprocess
        self._hookenv = hookenv
        self._host = host
        self._templating = templating
        self._execd = execd
        self._apt = apt

    def install_deps(self):
        """Install the deb dependencies of the Jenkins package."""

        # XXX This is for backward compatibility, since the the pre-layered
        #     version of this charm used a custom exec.d dir, and we want
        #     custom forks of that version to keep working unmodified in
        #     case they merge the code from the new layered charm.
        self._execd.execd_preinstall("hooks/install.d")

        self._hookenv.log("Installing jenkins dependencies.", level=DEBUG)
        self._apt.queue_install(APT_JENKINS_DEPS)

    def install_jenkins(self):
        """Install the Jenkins package."""
        self._hookenv.log("Installing jenkins.", level=DEBUG)
        config = self._hookenv.config()
        release = config["release"]
        if release == "bundle":
            self._install_from_bundle()
        elif release.startswith('http'):
            self._install_from_remote_deb(release)
        else:
            self._setup_source(release)
        self._apt.queue_install(["jenkins"])

    def configure_admin_user(self):
        """Configure the admin user."""
        # Always run - even if config has not changed, it's safe.
        self._hookenv.log("Configuring user for jenkins.", level=DEBUG)

        config = self._hookenv.config()
        admin_passwd = config["password"] or self._host.pwgen(length=15)

        self._host.write_file(
            JENKINS_PASSWORD_FILE, admin_passwd.encode("utf-8"), perms=0o0600)

        # Generate Salt and Hash Password for Jenkins
        salt = self._host.pwgen(length=6)
        sha = hashlib.sha256(("%s{%s}" % (admin_passwd, salt)).encode("utf-8"))
        salty_password = "%s:%s" % (salt, sha.hexdigest())

        self._host.mkdir(JENKINS_USERS, owner="jenkins", group="nogroup")

        admin_username = config["username"]
        admin_user_home = os.path.join(JENKINS_USERS, admin_username)
        self._host.mkdir(admin_user_home, owner="jenkins", group="nogroup")

        # NOTE: overwriting will destroy any data added by jenkins or the user.
        admin_user_config = os.path.join(admin_user_home, 'config.xml')
        context = {"username": admin_username, "password": salty_password}
        self._templating.render(
                "user-config.xml", admin_user_config, context,
                owner="jenkins", group="nogroup")

    def configure_server(self):
        """Generate Jenkins' config, if it hasn't done yet."""
        config = self._hookenv.config()

        # Only run on first invocation otherwise we blast
        # any configuration changes made
        if not config.get("_config-bootstrapped"):
            self._hookenv.log(
                "Bootstrapping secure initial configuration in Jenkins.",
                level=DEBUG)
            context = {"master_executors": config["master-executors"]}
            self._templating.render(
                "jenkins-config.xml", JENKINS_CONFIG_FILE, context,
                owner="jenkins", group="nogroup")
            # Touch
            config["_config-bootstrapped"] = True

        self._hookenv.log("Stopping jenkins for plugin update(s)", level=DEBUG)

    def install_plugins(self):
        self._host.service_stop("jenkins")
        self._install_jenkins_plugins()
        self._hookenv.log(
            "Starting jenkins to pickup configuration changes", level=DEBUG)
        self._host.service_start("jenkins")

    def install_tools(self):
        self._hookenv.log("Installing tools.", level=DEBUG)
        tools = self._hookenv.config()["tools"] or ""
        self._apt.queue_install(["python-jenkins"] + tools.split())

    def _install_from_bundle(self):
        """Install Jenkins from bundled package."""
        # Check bundled package exists.
        charm_dir = self._hookenv.charm_dir()
        bundle_path = os.path.join(charm_dir, "files", "jenkins.deb")
        if not os.path.isfile(bundle_path):
            message = "'%s' doesn't exist. No package bundled." % (bundle_path)
            raise Exception(message)
        self._hookenv.log(
            "Installing from bundled Jenkins package: %s:" % bundle_path)
        self._install_local_deb(bundle_path)

    def _install_local_deb(self, filename):
        """Install the given local jenkins deb"""
        # Run dpkg to install bundled deb.
        self._subprocess.check_call(("dpkg", "-i", filename))

    def _install_from_remote_deb(self, url):
        """Install Jenkins from http(s) deb file."""
        self._hookenv.log("Getting remote jenkins package: %s" % url)
        tempdir = tempfile.mkdtemp()
        target = os.path.join(tempdir, 'jenkins.deb')
        self._subprocess.check_call(("wget", "-q", "-O", target, url))
        self._install_local_deb(target)
        shutil.rmtree(tempdir)

    def _setup_source(self, release):
        """Install Jenkins archive."""
        self._hookenv.log("Configuring source of jenkins as %s" % release)

        # Configure to use upstream archives
        # lts - debian-stable
        # trunk - debian
        if release == "lts":
            dist = "debian-stable"
        elif release == "trunk":
            dist = "debian"
        else:
            message = "Release '%s' configuration not recognised" % (release)
            raise Exception(message)

        # Setup archive to use appropriate jenkins upstream
        wget = ("wget", "-q", "-O", "-", APT_JENKINS_KEY % dist)
        source = APT_JENKINS_SOURCE % dist
        key = self._subprocess.check_output(wget).decode("utf-8")
        self._apt.add_source(source, key=key)

    def _install_jenkins_plugins(self, plugins=None):
        config = self._hookenv.config()
        plugins = plugins or config["plugins"]
        if plugins:
            plugins = plugins.split()
        else:
            plugins = []
        self._hookenv.log(
            "Installing plugins (%s)" % (' '.join(plugins)), level=DEBUG)
        self._host.mkdir(
            JENKINS_PLUGINS, owner="jenkins", group="jenkins", perms=0o0755)

        track_dir = tempfile.mkdtemp(prefix='/tmp/plugins.installed')
        try:
            installed_plugins = glob.glob("%s/*.hpi" % (JENKINS_PLUGINS))
            for plugin in installed_plugins:
                # Create a ref of installed plugin
                ref_file = os.path.join(track_dir, os.path.basename(plugin))
                with open(ref_file, "w"):
                    pass

            plugins_site = config["plugins-site"]
            self._hookenv.log(
                "Fetching plugins from %s" % (plugins_site), level=DEBUG)
            # NOTE: by default wget verifies certificates as of 1.10.
            if config["plugins-check-certificate"] == "no":
                opts = ("--no-check-certificate",)
            else:
                opts = ()

            for plugin in plugins:
                plugin_filename = "%s.hpi" % (plugin)
                url = os.path.join(plugins_site, plugin_filename)
                plugin_path = os.path.join(JENKINS_PLUGINS, plugin_filename)
                if not os.path.isfile(plugin_path):
                    self._hookenv.log(
                        "Installing plugin %s" % (plugin_filename))
                    cmd = ("wget",) + opts + ("-q", "-O", "-", url)
                    plugin_data = self._subprocess.check_output(cmd)
                    self._host.write_file(
                        plugin_path, plugin_data, owner="jenkins",
                        group="jenkins", perms=0o0744)

                else:
                    self._hookenv.log(
                        "Plugin %s already installed" % (plugin_filename))

                ref = os.path.join(track_dir, plugin_filename)
                if os.path.exists(ref):
                    # Delete ref since plugin is installed.
                    os.remove(ref)

            installed_plugins = os.listdir(track_dir)
            if installed_plugins:
                if config["remove-unlisted-plugins"] == "yes":
                    for plugin in installed_plugins:
                        path = os.path.join(JENKINS_HOME, 'plugins', plugin)
                        if os.path.isfile(path):
                            self._hookenv.log(
                                "Deleting unlisted plugin '%s'" % (path))
                            os.remove(path)
                else:
                    self._hookenv.log(
                        "Unlisted plugins: (%s) Not removed. Set "
                        "remove-unlisted-plugins to 'yes' to clear them "
                        "away." % ", ".join(installed_plugins))

        finally:
            # Delete install refs
            shutil.rmtree(track_dir)
