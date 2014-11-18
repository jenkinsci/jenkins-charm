#!/usr/bin/env python

import os
import sys
import subprocess
from charmhelpers.core import hookenv


def default_execd_dir():
    return os.path.join(os.environ['CHARM_DIR'], 'exec.d')


def execd_module_paths(execd_dir=None):
    """Generate a list of full paths to modules within execd_dir."""
    if not execd_dir:
        execd_dir = default_execd_dir()

    if not os.path.exists(execd_dir):
        return

    for subpath in os.listdir(execd_dir):
        module = os.path.join(execd_dir, subpath)
        if os.path.isdir(module):
            yield module


def execd_submodule_paths(command, execd_dir=None):
    """Generate a list of full paths to the specified command within exec_dir.
    """
    for module_path in execd_module_paths(execd_dir):
        path = os.path.join(module_path, command)
        if os.access(path, os.X_OK) and os.path.isfile(path):
            yield path


def execd_run(command, execd_dir=None, die_on_error=False, stderr=None):
    """Run command for each module within execd_dir which defines it."""
    for submodule_path in execd_submodule_paths(command, execd_dir):
        try:
            subprocess.check_call(submodule_path, shell=True, stderr=stderr)
        except subprocess.CalledProcessError as e:
            hookenv.log("Error ({}) running  {}. Output: {}".format(
                e.returncode, e.cmd, e.output))
            if die_on_error:
                sys.exit(e.returncode)


def execd_preinstall(execd_dir=None):
    """Run charm-pre-install for each module within execd_dir."""
    execd_run('charm-pre-install', execd_dir=execd_dir)
