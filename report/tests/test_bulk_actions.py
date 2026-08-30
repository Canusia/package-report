from unittest.mock import patch

from django.test import Client, TestCase

from ..models.report import ReportScheduler
from .factories import login, make_report, make_scheduler, make_user

URL = '/ce/reports/bulk_actions'


class BulkRunTests(TestCase):
    def setUp(self):
        self.client = Client()
        login(self.client, make_user('root', superuser=True))
        self.report = make_report()
        self.alice = make_user('alice')

    def test_queues_pending_and_skips_the_rest(self):
        pending = make_scheduler(self.report, self.alice, status='pending')
        ran = make_scheduler(self.report, self.alice, status='ran')

        with patch('report.report.actions.process_report') as task:
            resp = self.client.post(URL, {
                'action': 'bulk_run_reports',
                'ids[]': [str(pending.id), str(ran.id)],
            })

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['outcome'], 'call')
        self.assertEqual(body['fn'], 'refreshTable')
        task.enqueue.assert_called_once_with(str(pending.id))
        self.assertIn('Queued 1', body['args']['message'])
        self.assertIn('skipped 1', body['args']['message'])

    def test_malformed_uuid_does_not_500(self):
        with patch('report.report.actions.process_report') as task:
            resp = self.client.post(URL, {
                'action': 'bulk_run_reports', 'ids[]': ['not-a-uuid'],
            })
        self.assertEqual(resp.status_code, 200)
        task.enqueue.assert_not_called()

    def test_non_superuser_denied(self):
        client = Client()
        login(client, make_user('plain_ce'))
        pending = make_scheduler(self.report, self.alice)
        resp = client.post(URL, {
            'action': 'bulk_run_reports', 'ids[]': [str(pending.id)]})
        self.assertEqual(resp.status_code, 403)

    def test_unknown_action_rejected(self):
        resp = self.client.post(URL, {'action': 'drop_everything'})
        self.assertEqual(resp.status_code, 400)


class BulkDeleteTests(TestCase):
    def setUp(self):
        self.client = Client()
        login(self.client, make_user('root', superuser=True))
        self.report = make_report()
        self.alice = make_user('alice')

    def test_phase_one_returns_a_confirmation_modal(self):
        pending = make_scheduler(self.report, self.alice)
        resp = self.client.post(URL, {
            'action': 'bulk_delete_reports', 'ids[]': [str(pending.id)]})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['outcome'], 'modal')
        self.assertIn('bulk_delete_reports', body['html'])
        self.assertTrue(
            ReportScheduler.objects.filter(pk=pending.id).exists())

    def test_phase_two_deletes_pending_only(self):
        pending = make_scheduler(self.report, self.alice, status='pending')
        ran = make_scheduler(self.report, self.alice, status='ran')

        resp = self.client.post(URL, {
            'action': 'bulk_delete_reports',
            'action_confirmed': '1',
            'confirm': 'on',
            'ids[]': [str(pending.id), str(ran.id)],
        })

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['fn'], 'refreshTable')
        self.assertFalse(
            ReportScheduler.objects.filter(pk=pending.id).exists())
        self.assertTrue(ReportScheduler.objects.filter(pk=ran.id).exists())

    def test_non_superuser_denied(self):
        client = Client()
        login(client, make_user('plain_ce'))
        pending = make_scheduler(self.report, self.alice)
        resp = client.post(URL, {
            'action': 'bulk_delete_reports', 'ids[]': [str(pending.id)]})
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(
            ReportScheduler.objects.filter(pk=pending.id).exists())
