import os
import subprocess

from charmhelpers.core.hookenv import log

from charms.layer.jenkins import paths


class Storage(object):
    _backup_dir = paths.HOME + '.bak'

    def _clone_ownership(self, src, dest):
        """
        Set the user and group of dest to the same as src.
        """
        src_stat = os.stat(src)
        os.chown(dest, src_stat.st_uid, src_stat.st_gid)

    def link_home(self, dest):
        if os.path.exists(paths.HOME):
            # A couple of these will never be hit in real life, given the
            # current storage config and latest version of Juju. They are
            # included for completeness if either of those change or manual
            # changes are made.
            self._clone_ownership(paths.HOME, dest)
            if os.path.islink(paths.HOME):
                os.remove(paths.HOME)
            else:
                # If the Jenkins home is a directory we either move it to the
                # dest or move it to a backup location.
                if os.stat(paths.HOME).st_dev == os.stat(dest).st_dev and \
                   len(os.listdir(dest)) == 0:
                    # This handles the simple case of upgrading from a charm
                    # version with no storage support to one with it
                    for f in os.listdir(paths.HOME):
                        # Note os.rename doesn't work depending on the type of
                        # mount, shutil.move doesn't preserve owner/group
                        subprocess.check_call(["mv",
                                               os.path.join(paths.HOME, f),
                                               os.path.join(dest, f)])
                    os.rmdir(paths.HOME)
                else:
                    if os.path.exists(self._backup_dir):
                        raise RuntimeError('{} exists, failed moving storage.'.
                                           format(self._backup_dir))
                    os.rename(paths.HOME, self._backup_dir)

        os.symlink(dest, paths.HOME)

    def unlink_home(self):
        if not os.path.islink(paths.HOME):
            log("{} is not a symbolic link, skipping.".format(paths.HOME))
            return

        if not os.path.exists(self._backup_dir):
            os.makedirs(self._backup_dir, 0o755)
            self._clone_ownership(paths.HOME, self._backup_dir)

        os.remove(paths.HOME)
        os.rename(self._backup_dir, paths.HOME)
