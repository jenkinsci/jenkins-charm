# Bootstrap charm-helpers, installing its dependencies if necessary using
# only standard libraries.
import subprocess
import sys

try:
    import six  # flake8: noqa
except ImportError:
    if sys.version_info.major == 2:
        subprocess.check_call(['apt-get', 'install', '-y', 'python-six'])
    else:
        subprocess.check_call(['apt-get', 'install', '-y', 'python3-six'])
    import six  # flake8: noqa

try:
    import yaml  # flake8: noqa
except ImportError:
    if sys.version_info.major == 2:
        subprocess.check_call(['apt-get', 'install', '-y', 'python-yaml'])
    else:
        subprocess.check_call(['apt-get', 'install', '-y', 'python3-yaml'])
    import yaml  # flake8: noqa
