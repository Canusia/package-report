"""run_command executes arbitrary Django management commands.

It shipped with no role check at all — `cis.middleware.LoginRequiredMiddleware`
enforces login but not any role, so every authenticated user, including a
student, could run any no-argument management command in the deployment.
It is now superuser-only.
"""
from unittest.mock import patch

from django.test import Client, TestCase

from .factories import login, make_report, make_scheduler, make_user

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


class RunReportAuthzTests(TestCase):
    """run_report executes one scheduler row synchronously and emails its
    requester. It shipped with no role check, so any authenticated user could
    trigger anyone else's queued report. Its only caller is the
    ReportScheduler admin changelist's run_report_link column, so superuser
    matches its actual audience."""

    def setUp(self):
        self.scheduler = make_scheduler(make_report(), make_user('owner'))
        self.url = f'/ce/reports/run_report/{self.scheduler.id}'

    def _as(self, user):
        client = Client()
        login(client, user)
        return client

    def test_superuser_may_run_any_scheduled_report(self):
        """Including one requested by somebody else — the row here belongs to
        'owner', not to the superuser running it."""
        client = self._as(make_user('root', superuser=True))
        self.assertNotEqual(self.scheduler.created_by.username, 'root')
        with patch.object(type(self.scheduler), 'run') as run:
            resp = client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        run.assert_called_once()

    def test_student_may_not_run_a_report(self):
        client = self._as(make_user('pupil', groups=('student',)))
        with patch.object(type(self.scheduler), 'run') as run:
            resp = client.get(self.url)
        self.assertEqual(resp.status_code, 302)
        run.assert_not_called()

    def test_ce_staff_may_not_run_a_report(self):
        client = self._as(make_user('ce_staff'))
        with patch.object(type(self.scheduler), 'run') as run:
            resp = client.get(self.url)
        self.assertEqual(resp.status_code, 302)
        run.assert_not_called()

    def test_owner_without_superuser_may_not_run_it_directly(self):
        """Even the row's own requester goes through the normal scheduling
        flow, not this admin-only endpoint."""
        client = self._as(make_user('owner2'))
        with patch.object(type(self.scheduler), 'run') as run:
            resp = client.get(self.url)
        self.assertEqual(resp.status_code, 302)
        run.assert_not_called()

    def test_anonymous_may_not_run_a_report(self):
        with patch.object(type(self.scheduler), 'run') as run:
            resp = Client().get(self.url)
        self.assertEqual(resp.status_code, 302)
        run.assert_not_called()
