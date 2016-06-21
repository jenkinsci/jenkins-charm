"""Jenkins-related file system paths."""

import os

HOME = "/var/lib/jenkins"
USERS = os.path.join(HOME, "users")
PLUGINS = os.path.join(HOME, "plugins")
PASSWORD_FILE = os.path.join(HOME, ".admin_password")
CONFIG_FILE = os.path.join(HOME, "config.xml")
