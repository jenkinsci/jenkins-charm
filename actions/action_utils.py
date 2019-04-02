import sys
import time

from charmhelpers.core import hookenv, host


def _wait_for_jenkins(state, timeout):
    """
    Wait for the host jenkins service to settle to a given state.

    :param: string state: Desired state of the jenkins service, 'started' or
                          'stopped'.
    :param: int timeout: Seconds to wait for desired state.
    """
    start = time.time()
    while time.time() - start < timeout:
        up = host.service_running('jenkins')
        if (state is "started" and up) or (state is "stopped" and not up):
            return True
        time.sleep(5)
    return False


def fail(msg, output=None):
    """Fail an action with a message and (optionally) additional output."""
    if output:
        hookenv.action_set({'output': output})
    hookenv.action_fail(msg)
    sys.exit()


def fail_if_started(timeout=60):
    """
    Fail an action if the jenkins service does not stop in the given time.

    If the service is already stopped, do nothing. If it is running, stop
    the service. If it does not stop in the given time, fail the action.

    :param: int timeout: Seconds to wait for jenkins to stop.
    """
    if host.service_running('jenkins'):
        host.service_stop('jenkins')
        if not _wait_for_jenkins(state='stopped', timeout=timeout):
            error = 'Jenkins did not stop.'
            detail = ('The action tried to stop the jenkins service, but it '
                      'did not stop in the given time. The action did not '
                      'proceed.')
            fail(error, detail)


def fail_if_stopped(timeout=60):
    """
    Fail an action if the jenkins service does not start in the given time.

    If the service is already started, do nothing. If it is not running,
    start the service. If it does not start in the given time, fail the action.

    :param: int timeout: Seconds to wait for jenkins to start.
    """
    if not host.service_running('jenkins'):
        host.service_start('jenkins')
        if not _wait_for_jenkins(state='started', timeout=timeout):
            error = 'Jenkins did not start.'
            detail = ('The action stopped the jenkins service and completed. '
                      'However, it was unable to start the service after '
                      'completion. Jenkins is currently stopped.')
            fail(error, detail)
