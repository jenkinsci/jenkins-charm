"""Jenkins-related file system paths."""

import os

HOME = "/var/lib/jenkins"
USERS = os.path.join(HOME, "users")
PLUGINS = os.path.join(HOME, "plugins")
CONFIG_FILE = os.path.join(HOME, "config.xml")
ADMIN_TOKEN = os.path.join(HOME, ".admin_token")
ADMIN_PASSWORD = os.path.join(HOME, ".admin_password")
