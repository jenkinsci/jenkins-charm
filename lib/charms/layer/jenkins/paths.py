"""Jenkins-related file system paths."""

import os

HOME = "var/lib/jenkins"
USERS = os.path.join(HOME, "users")
PLUGINS = os.path.join(HOME, "plugins")
CONFIG_FILE = os.path.join(HOME, "config.xml")


def root():
    return os.environ.get("TEST_ROOT_DIR", "/")


def home():
    return os.path.join(root(), HOME)


def users():
    return os.path.join(root(), USERS)


def plugins():
    return os.path.join(root(), PLUGINS)


def config_file():
    return os.path.join(home(), "config.xml")


def admin_token():
    return os.path.join(home(), ".admin_token")


def admin_password():
    return os.path.join(home(), ".admin_password")
