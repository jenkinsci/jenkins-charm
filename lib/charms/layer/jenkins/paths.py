"""Jenkins-related file system paths."""

import os

HOME = "/var/lib/jenkins"
USERS = os.path.join(HOME, "users")
PLUGINS = os.path.join(HOME, "plugins")
PLUGINS_BACKUP = os.path.join(HOME, "plugins_charm_backup")
SECRETS = os.path.join(HOME, "secrets")
CONFIG_FILE = os.path.join(HOME, "config.xml")
LOCATION_CONFIG_FILE =\
    os.path.join(HOME, "jenkins.model.JenkinsLocationConfiguration.xml")
DEFAULTS_CONFIG_FILE = "/etc/default/jenkins"
ADMIN_TOKEN = os.path.join(HOME, ".admin_token")
ADMIN_PASSWORD = os.path.join(HOME, ".admin_password")
INITIAL_PASSWORD = os.path.join(SECRETS, "initialAdminPassword")
LAST_EXEC = os.path.join(HOME, "jenkins.install.InstallUtil.lastExecVersion")
LEGACY_BOOTSTRAP_FLAG = os.path.join(HOME, "config.bootstrapped")
UPDATE_CENTER_ROOT_CAS = os.path.join(HOME, "update-center-rootCAs")
