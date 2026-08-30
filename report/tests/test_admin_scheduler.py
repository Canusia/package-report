from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from .factories import login, make_report, make_scheduler, make_user


class RunPendingActionTests(TestCase):
    def setUp(self):
        self.client = Client()
        login(self.client, make_user('root', superuser=True))
        self.report = make_report()
        self.user = make_user('alice')

    def _run_action(self, schedulers):
        return self.client.post(
            reverse('admin:report_reportscheduler_changelist'),
            {
                'action': 'run_selected_pending_reports',
                '_selected_action': [str(s.id) for s in schedulers],
            },
            follow=True,
        )

    def test_queues_only_pending_rows(self):
        pending = make_scheduler(self.report, self.user, status='pending')
        already_ran = make_scheduler(self.report, self.user, status='ran')

        with patch('report.report.actions.process_report') as task:
            resp = self._run_action([pending, already_ran])

        self.assertEqual(resp.status_code, 200)
        task.enqueue.assert_called_once_with(str(pending.id))
        self.assertContains(
            resp, 'Queued 1 report(s); skipped 1 that were not pending.')

    def test_no_pending_rows_queues_nothing(self):
        ran = make_scheduler(self.report, self.user, status='ran')
        with patch('report.report.actions.process_report') as task:
            self._run_action([ran])
        task.enqueue.assert_not_called()


class SchedulerAdminDisplayTests(TestCase):
    def setUp(self):
        self.client = Client()
        login(self.client, make_user('root', superuser=True))

    def test_data_is_truncated_not_dumped_raw(self):
        scheduler = make_scheduler(make_report(), make_user('alice'))
        scheduler.data = {'term': ['x' * 500]}
        scheduler.save()
        resp = self.client.get(
            reverse('admin:report_reportscheduler_changelist'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('x' * 200, resp.content.decode())
