"""`templates/reports/index.html` serves every portal, but its AJAX endpoints
were written as `{% url 'report:...' %}` — the CE namespace — so a school
admin on /highschool_admin/reports/ posted their category lookups, form loads
and report submissions into /ce/reports/. That only worked because those CE
views carry no role check; it also meant the HS admin portal's own routes were
never exercised.

The page must address the portal it is being served from.
"""
from django.test import Client, TestCase

from .factories import login, make_user


class PortalNamespaceTests(TestCase):
    def _body(self, user, url):
        client = Client()
        login(client, user)
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    def test_ce_page_posts_to_the_ce_routes(self):
        body = self._body(make_user('ce_user', groups=('ce',)), '/ce/reports/')
        for endpoint in ('reports_in_category', 'report_details', 'schedule_report'):
            self.assertIn(f'/ce/reports/{endpoint}/', body)

    def test_highschool_admin_page_posts_to_the_highschool_admin_routes(self):
        body = self._body(
            make_user('hs_user', groups=('highschool_admin',)),
            '/highschool_admin/reports/',
        )
        for endpoint in ('reports_in_category', 'report_details', 'schedule_report'):
            self.assertIn(f'/highschool_admin/reports/{endpoint}/', body)
            self.assertNotIn(f'/ce/reports/{endpoint}/', body)
