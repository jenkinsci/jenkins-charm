import os
import hashlib

from collections import namedtuple

from charmhelpers.core import hookenv
from charmhelpers.core import host
from charmhelpers.core import templating
from charmhelpers.core.hookenv import DEBUG

from paths import (
    USERS,
    PASSWORD_FILE,
)


class Users(object):

    def __init__(self, hookenv=hookenv, host=host, templating=templating):
        self._hookenv = hookenv
        self._host = host
        self._templating = templating

    def configure_admin(self):
        """Configure the admin user."""
        # Always run - even if config has not changed, it's safe.
        self._hookenv.log("Configuring user for jenkins.", level=DEBUG)

        admin = self._admin_data()

        self._host.write_file(
            PASSWORD_FILE, admin.password.encode("utf-8"), perms=0o0600)

        self._host.mkdir(USERS, owner="jenkins", group="nogroup")

        admin_home = os.path.join(USERS, admin.username)
        self._host.mkdir(admin_home, owner="jenkins", group="nogroup")

        # NOTE: overwriting will destroy any data added by jenkins or the user.
        admin_config = os.path.join(admin_home, 'config.xml')
        context = {
            "username": admin.username, "password": admin.salty_password}
        self._templating.render(
            "user-config.xml", admin_config, context, owner="jenkins",
            group="nogroup")

    def _admin_data(self):
        config = self._hookenv.config()
        username = config["username"]
        password = config["password"] or self._host.pwgen(length=15)

        # Generate Salt and Hash Password for Jenkins
        salt = self._host.pwgen(length=6)
        sha = hashlib.sha256(("%s{%s}" % (password, salt)).encode("utf-8"))
        salty_password = "%s:%s" % (salt, sha.hexdigest())

        return _User(username, password, salty_password)


_User = namedtuple("User", ["username", "password", "salty_password"])
