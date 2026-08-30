from django.test import Client, TestCase
from django.urls import reverse

from .factories import login, make_report, make_user


class ReportAdminListTests(TestCase):
    def setUp(self):
        self.user = make_user('root', superuser=True)
        self.client = Client()
        login(self.client, self.user)

    def test_changelist_shows_title_and_label_columns(self):
        make_report(
            title='Class Roster Export',
            categories=['Classes', 'Students'],
            available_for=['ce', 'highschool_admin'],
        )
        resp = self.client.get(reverse('admin:report_report_changelist'))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('Class Roster Export', body)
        self.assertIn('Classes, Students', body)
        # Labels, not raw values.
        self.assertIn('EC Staff, High School Administrator', body)

    def test_search_matches_title(self):
        make_report(title='Findable Report')
        make_report(title='Other Report')
        resp = self.client.get(
            reverse('admin:report_report_changelist'), {'q': 'Findable'})
        self.assertContains(resp, 'Findable Report')
        self.assertNotContains(resp, 'Other Report')
