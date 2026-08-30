from django.test import Client, TestCase

from ..models.report import Report
from .factories import login, make_report, make_user

URL = '/ce/reports/update_report/'


class UpdateReportTests(TestCase):
    def setUp(self):
        self.client = Client()
        login(self.client, make_user('root', superuser=True))
        self.report = make_report(
            title='Before', categories=['Students'], available_for=['ce'])

    def _post(self, **overrides):
        payload = {
            'report_id': str(self.report.id),
            'title': 'After',
            'description': 'Updated description',
            'categories': ['Classes', 'Misc.'],
            'available_for': ['ce', 'instructor'],
        }
        payload.update(overrides)
        return self.client.post(URL, payload)

    def test_updates_categories_and_available_for(self):
        resp = self._post()
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['status'], 'success')
        self.assertEqual(body['categories'], ['Classes', 'Misc.'])
        self.assertEqual(body['available_for'], ['ce', 'instructor'])

        self.report.refresh_from_db()
        self.assertEqual(self.report.title, 'After')
        self.assertEqual(list(self.report.categories), ['Classes', 'Misc.'])
        self.assertEqual(list(self.report.available_for), ['ce', 'instructor'])

    def test_rejects_unknown_category(self):
        resp = self._post(categories=['Students', 'Not A Category'])
        self.assertEqual(resp.status_code, 400)
        self.assertIn('category', resp.json()['message'].lower())
        self.report.refresh_from_db()
        self.assertEqual(list(self.report.categories), ['Students'])

    def test_rejects_unknown_role(self):
        resp = self._post(available_for=['ce', 'wizard'])
        self.assertEqual(resp.status_code, 400)
        self.assertIn('role', resp.json()['message'].lower())

    def test_rejects_empty_categories(self):
        resp = self._post(categories=[])
        self.assertEqual(resp.status_code, 400)

    def test_rejects_empty_available_for(self):
        resp = self._post(available_for=[])
        self.assertEqual(resp.status_code, 400)

    def test_unique_together_collision_returns_400_not_500(self):
        Report.objects.create(
            app='cis', name=self.report.name, title='Twin',
            description='x', categories=['Classes', 'Misc.'],
            available_for=['ce'])
        resp = self._post()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('already exists', resp.json()['message'])

    def test_non_superuser_denied(self):
        client = Client()
        login(client, make_user('plain_ce'))
        resp = client.post(URL, {
            'report_id': str(self.report.id), 'title': 'Hacked',
            'categories': ['Classes'], 'available_for': ['ce'],
        })
        self.assertEqual(resp.status_code, 403)
        self.report.refresh_from_db()
        self.assertEqual(self.report.title, 'Before')


class ReportDetailsContextTests(TestCase):
    def test_details_exposes_choice_lists(self):
        client = Client()
        login(client, make_user('root', superuser=True))
        report = make_report(name='teacher_certificates')
        resp = client.get('/ce/reports/report_details/',
                          {'report_id': str(report.id)})
        html = resp.json()['report']
        self.assertIn('edit-report-categories', html)
        self.assertIn('edit-report-available-for', html)
        self.assertIn('High School Administrator', html)
