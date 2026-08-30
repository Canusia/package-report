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


class AnalyticsAjaxFormatTests(TestCase):
    """The scheduled-reports table must ask for the datatables envelope.

    Without `format=datatables` the endpoint returns DRF's plain page shape
    ({count, next, previous, results}), which has no `data` key. DataTables
    then reads json.data.length and throws
    "Cannot read properties of undefined (reading 'length')".
    """

    def test_scheduled_table_requests_datatables_format(self):
        client = Client()
        login(client, make_user('root', superuser=True))
        body = client.get('/ce/reports/').content.decode()

        analytics_script = body.split('id="pane-analytics"', 1)[1]
        self.assertIn("d.format = 'datatables'", analytics_script)
