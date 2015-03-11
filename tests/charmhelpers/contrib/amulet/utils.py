import ConfigParser
import io
import logging
import re
import sys
import time

import six


class AmuletUtils(object):
    """Amulet utilities.

       This class provides common utility functions that are used by Amulet
       tests.
       """

    def __init__(self, log_level=logging.ERROR):
        self.log = self.get_logger(level=log_level)

    def get_logger(self, name="amulet-logger", level=logging.DEBUG):
        """Get a logger object that will log to stdout."""
        log = logging
        logger = log.getLogger(name)
        fmt = log.Formatter("%(asctime)s %(funcName)s "
                            "%(levelname)s: %(message)s")

        handler = log.StreamHandler(stream=sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(fmt)

        logger.addHandler(handler)
        logger.setLevel(level)

        return logger

    def valid_ip(self, ip):
        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
            return True
        else:
            return False

    def valid_url(self, url):
        p = re.compile(
            r'^(?:http|ftp)s?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # noqa
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$',
            re.IGNORECASE)
        if p.match(url):
            return True
        else:
            return False

    def validate_services(self, commands):
        """Validate services.

           Verify the specified services are running on the corresponding
           service units.
           """
        for k, v in six.iteritems(commands):
            for cmd in v:
                output, code = k.run(cmd)
                if code != 0:
                    return "command `{}` returned {}".format(cmd, str(code))
        return None

    def _get_config(self, unit, filename):
        """Get a ConfigParser object for parsing a unit's config file."""
        file_contents = unit.file_contents(filename)
        config = ConfigParser.ConfigParser()
        config.readfp(io.StringIO(file_contents))
        return config

    def validate_config_data(self, sentry_unit, config_file, section,
                             expected):
        """Validate config file data.

           Verify that the specified section of the config file contains
           the expected option key:value pairs.
           """
        config = self._get_config(sentry_unit, config_file)

        if section != 'DEFAULT' and not config.has_section(section):
            return "section [{}] does not exist".format(section)

        for k in expected.keys():
            if not config.has_option(section, k):
                return "section [{}] is missing option {}".format(section, k)
            if config.get(section, k) != expected[k]:
                return "section [{}] {}:{} != expected {}:{}".format(
                       section, k, config.get(section, k), k, expected[k])
        return None

    def _validate_dict_data(self, expected, actual):
        """Validate dictionary data.

           Compare expected dictionary data vs actual dictionary data.
           The values in the 'expected' dictionary can be strings, bools, ints,
           longs, or can be a function that evaluate a variable and returns a
           bool.
           """
        for k, v in six.iteritems(expected):
            if k in actual:
                if (isinstance(v, six.string_types) or
                        isinstance(v, bool) or
                        isinstance(v, six.integer_types)):
                    if v != actual[k]:
                        return "{}:{}".format(k, actual[k])
                elif not v(actual[k]):
                    return "{}:{}".format(k, actual[k])
            else:
                return "key '{}' does not exist".format(k)
        return None

    def validate_relation_data(self, sentry_unit, relation, expected):
        """Validate actual relation data based on expected relation data."""
        actual = sentry_unit.relation(relation[0], relation[1])
        self.log.debug('actual: {}'.format(repr(actual)))
        return self._validate_dict_data(expected, actual)

    def _validate_list_data(self, expected, actual):
        """Compare expected list vs actual list data."""
        for e in expected:
            if e not in actual:
                return "expected item {} not found in actual list".format(e)
        return None

    def not_null(self, string):
        if string is not None:
            return True
        else:
            return False

    def _get_file_mtime(self, sentry_unit, filename):
        """Get last modification time of file."""
        return sentry_unit.file_stat(filename)['mtime']

    def _get_dir_mtime(self, sentry_unit, directory):
        """Get last modification time of directory."""
        return sentry_unit.directory_stat(directory)['mtime']

    def _get_proc_start_time(self, sentry_unit, service, pgrep_full=False):
        """Get process' start time.

           Determine start time of the process based on the last modification
           time of the /proc/pid directory. If pgrep_full is True, the process
           name is matched against the full command line.
           """
        if pgrep_full:
            cmd = 'pgrep -o -f {}'.format(service)
        else:
            cmd = 'pgrep -o {}'.format(service)
        proc_dir = '/proc/{}'.format(sentry_unit.run(cmd)[0].strip())
        return self._get_dir_mtime(sentry_unit, proc_dir)

    def service_restarted(self, sentry_unit, service, filename,
                          pgrep_full=False, sleep_time=20):
        """Check if service was restarted.

           Compare a service's start time vs a file's last modification time
           (such as a config file for that service) to determine if the service
           has been restarted.
           """
        time.sleep(sleep_time)
        if (self._get_proc_start_time(sentry_unit, service, pgrep_full) >=
                self._get_file_mtime(sentry_unit, filename)):
            return True
        else:
            return False

    def relation_error(self, name, data):
        return 'unexpected relation data in {} - {}'.format(name, data)

    def endpoint_error(self, name, data):
        return 'unexpected endpoint data in {} - {}'.format(name, data)
