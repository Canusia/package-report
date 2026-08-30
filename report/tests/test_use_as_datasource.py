from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in

from cis.models.customuser import CustomUser
from report.report.models.report import Report


def _login(client, user):
    from django_login_history.models import post_login
    user_logged_in.disconnect(post_login)
    try:
        client.force_login(user)
    finally:
        user_logged_in.connect(post_login)


class UseAsDatasourceFlagTests(TestCase):
    """The 'Use as datasource' button is gated behind the default-off
    REPORTS_USE_AS_DATASOURCE_ENABLED flag (it needs a compatible announcement
    version with the handoff endpoint)."""

    def setUp(self):
        Group.objects.get_or_create(name='instructor')
        ce, _ = Group.objects.get_or_create(name='ce')
        self.user = CustomUser.objects.create(username='ce', email='ce@x.com')
        self.user.groups.add(ce)
        # teacher_certificates opts in via use_as_datasource = True
        self.report = Report.objects.create(
            app='cis', name='teacher_certificates',
            title='Teacher Course Certificates',
            description='x', categories=['Instructors'], available_for=['ce'])
        self.client = Client()
        _login(self.client, self.user)

    def _details_html(self):
        resp = self.client.get('/ce/reports/report_details/',
                               {'report_id': str(self.report.id)})
        self.assertEqual(resp.status_code, 200)
        return resp.json().get('report', '')

    @override_settings(REPORTS_USE_AS_DATASOURCE_ENABLED=False)
    def test_button_hidden_by_default(self):
        self.assertNotIn('Use as datasource', self._details_html())

    @override_settings(REPORTS_USE_AS_DATASOURCE_ENABLED=True)
    def test_button_shown_when_flag_enabled(self):
        self.assertIn('Use as datasource', self._details_html())
