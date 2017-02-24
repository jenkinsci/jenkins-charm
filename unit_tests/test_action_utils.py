#!/usr/bin/env python3

import unittest
from unittest import mock
from actions import action_utils


class TestActionUtils(unittest.TestCase):

    @mock.patch('actions.action_utils.hookenv.action_set')
    @mock.patch('actions.action_utils.hookenv.action_fail')
    @mock.patch('actions.action_utils.sys.exit')
    def test_fail(self, mock_sys_exit, mock_action_fail, mock_action_set):
        """
        Verify we fail cleanly and make expected action_* calls.
        """
        error = 'test'
        details = 'details'
        self.assertEqual(None, action_utils.fail(msg=error, output=details))
        mock_action_set.assert_called_once_with({'output': details})
        mock_action_fail.assert_called_once_with(error)

    @mock.patch('actions.action_utils.host.service_running')
    @mock.patch('actions.action_utils.host.service_stop')
    @mock.patch('actions.action_utils._wait_for_jenkins')
    @mock.patch('actions.action_utils.fail')
    def test_fail_if_started(self, mock_fail, mock_wait, mock_stop,
                             mock_running):
        """
        Test our failure path if we cannot stop jenkins.
        """
        # test when jenkins is already stopped
        mock_running.return_value = False
        self.assertEqual(None, action_utils.fail_if_started(5))
        mock_fail.assert_not_called()

        # test when jenkins is running and we succesfully stop it
        mock_running.return_value = True
        mock_wait.return_value = True
        self.assertEqual(None, action_utils.fail_if_started(5))
        mock_fail.assert_not_called()

        # test when jenkins is running and we do not stop it
        mock_running.return_value = True
        mock_wait.return_value = False
        self.assertEqual(None, action_utils.fail_if_started(5))
        args, kwargs = mock_fail.call_args
        mock_fail.assert_called_once_with(*args)

    @mock.patch('actions.action_utils.host.service_running')
    @mock.patch('actions.action_utils.host.service_start')
    @mock.patch('actions.action_utils._wait_for_jenkins')
    @mock.patch('actions.action_utils.fail')
    def test_fail_if_stopped(self, mock_fail, mock_wait, mock_start,
                             mock_running):
        """
        Test our failure path if we cannot start jenkins.
        """
        # test when jenkins is already started
        mock_running.return_value = True
        self.assertEqual(None, action_utils.fail_if_stopped(5))
        mock_fail.assert_not_called()

        # test when jenkins is stopped and we succesfully start it
        mock_running.return_value = False
        mock_wait.return_value = True
        self.assertEqual(None, action_utils.fail_if_stopped(5))
        mock_fail.assert_not_called()

        # test when jenkins is stopped and we do not start it
        mock_running.return_value = False
        mock_wait.return_value = False
        self.assertEqual(None, action_utils.fail_if_stopped(5))
        args, kwargs = mock_fail.call_args
        mock_fail.assert_called_once_with(*args)

    @mock.patch('actions.action_utils.host.service_running')
    def test_wait(self, mock_running):
        """
        Test our timer.
        """
        # test when jenkins is running
        mock_running.return_value = True
        self.assertTrue(action_utils._wait_for_jenkins('started', 5))
        self.assertFalse(action_utils._wait_for_jenkins('stopped', 5))

        # test when jenkins is stopped
        mock_running.return_value = False
        self.assertTrue(action_utils._wait_for_jenkins('stopped', 5))
        self.assertFalse(action_utils._wait_for_jenkins('started', 5))
