from django.test import Client, TestCase

from .factories import login, make_user


class AnalyticsTabVisibilityTests(TestCase):
    def _get(self, user):
        client = Client()
        login(client, user)
        return client.get('/ce/reports/')

    def test_superuser_sees_the_tab(self):
        resp = self._get(make_user('root', superuser=True))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('pane-analytics', body)
        self.assertIn('all_report_scheduler', body)
        self.assertIn('bulk_run_reports', body)

    def test_plain_ce_user_does_not_see_the_tab(self):
        body = self._get(make_user('plain_ce')).content.decode()
        self.assertNotIn('pane-analytics', body)
        self.assertNotIn('bulk_run_reports', body)
