from django.test import Client, TestCase
from django.urls import reverse

from .factories import login, make_report, make_scheduler, make_user


class ReportAdminRunCountTests(TestCase):
    def setUp(self):
        self.client = Client()
        login(self.client, make_user('root', superuser=True))
        self.report = make_report(title='Counted Report')

    def _change_url(self):
        return reverse('admin:report_report_change', args=[self.report.id])

    def test_counts_are_grouped_by_user_and_split_by_status(self):
        alice = make_user('alice')
        bob = make_user('bob')
        for _ in range(5):
            make_scheduler(self.report, alice, status='ran')
        for _ in range(10):
            make_scheduler(self.report, bob, status='ran')
        make_scheduler(self.report, bob, status='error')

        resp = self.client.get(self._change_url())
        self.assertEqual(resp.status_code, 200)
        rows = resp.context['run_counts']
        # Ordered by total descending: bob (11) before alice (5).
        self.assertEqual([r['email'] for r in rows],
                         ['bob@example.com', 'alice@example.com'])
        self.assertEqual(rows[0], {
            'name': 'Bob Tester', 'email': 'bob@example.com',
            'pending': 0, 'ran': 10, 'error': 1, 'total': 11,
        })
        self.assertEqual(rows[1]['ran'], 5)
        self.assertEqual(rows[1]['total'], 5)

    def test_counts_exclude_other_reports(self):
        other = make_report(title='Other')
        make_scheduler(other, make_user('carol'), status='ran')
        self.assertEqual(self.client.get(self._change_url())
                         .context['run_counts'], [])

    def test_never_run_message(self):
        self.assertContains(self.client.get(self._change_url()),
                            'This report has never been run.')
