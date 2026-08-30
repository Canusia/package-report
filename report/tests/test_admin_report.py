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


class ReportAdminFilterTests(TestCase):
    """MultiSelectField columns store "Classes,Students"; the default
    ChoicesFieldListFilter would build categories__exact and hide every
    multi-valued row from its own category filter."""

    def setUp(self):
        self.client = Client()
        login(self.client, make_user('root', superuser=True))
        self.url = reverse('admin:report_report_changelist')

    def test_multi_category_report_survives_a_category_filter(self):
        make_report(title='Two Category Report',
                    categories=['Classes', 'Students'])
        make_report(title='Misc Only Report', categories=['Misc.'])

        resp = self.client.get(self.url, {'categories': 'Classes'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Two Category Report')
        self.assertNotContains(resp, 'Misc Only Report')

        # ...and from the other category it belongs to.
        resp = self.client.get(self.url, {'categories': 'Students'})
        self.assertContains(resp, 'Two Category Report')

    def test_multi_role_report_survives_an_available_for_filter(self):
        make_report(title='Two Role Report',
                    available_for=['ce', 'highschool_admin'])
        make_report(title='Instructor Only Report',
                    available_for=['instructor'])

        resp = self.client.get(self.url, {'available_for': 'highschool_admin'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Two Role Report')
        self.assertNotContains(resp, 'Instructor Only Report')
