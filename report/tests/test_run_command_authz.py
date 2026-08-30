"""run_command executes arbitrary Django management commands.

It shipped with no role check at all — `cis.middleware.LoginRequiredMiddleware`
enforces login but not any role, so every authenticated user, including a
student, could run any no-argument management command in the deployment.
It is now superuser-only.
"""
from unittest.mock import patch

from django.test import Client, TestCase

from .factories import login, make_user

URL = '/ce/reports/run_command/register_reports'


class RunCommandAuthzTests(TestCase):
    def _as(self, user):
        client = Client()
        login(client, user)
        return client

    def test_superuser_may_run_a_command(self):
        client = self._as(make_user('root', superuser=True))
        with patch('django.core.management.call_command') as call_command:
            resp = client.get(URL)
        self.assertEqual(resp.status_code, 200)
        call_command.assert_called_once_with('register_reports')

    def test_student_may_not_run_a_command(self):
        client = self._as(make_user('pupil', groups=('student',)))
        with patch('django.core.management.call_command') as call_command:
            resp = client.get(URL)
        self.assertEqual(resp.status_code, 302)
        call_command.assert_not_called()

    def test_ce_staff_may_not_run_a_command(self):
        """CE role is not enough — this executes arbitrary management commands."""
        client = self._as(make_user('ce_staff'))
        with patch('django.core.management.call_command') as call_command:
            resp = client.get(URL)
        self.assertEqual(resp.status_code, 302)
        call_command.assert_not_called()

    def test_anonymous_may_not_run_a_command(self):
        with patch('django.core.management.call_command') as call_command:
            resp = Client().get(URL)
        self.assertEqual(resp.status_code, 302)
        call_command.assert_not_called()
