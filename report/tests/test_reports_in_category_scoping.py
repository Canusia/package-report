"""`get_reports_in_category` filtered on `available_for` for HS admins and
skipped the filter for CIS/CE, but had no else — so a student, instructor,
faculty or tech-center user got every report in the category, `available_for`
ignored entirely. `reports_in_category` is only @login_required, so that
listing was reachable, and #2 B2 made each listed report runnable.

Scoping is now expressed once, in Report.is_available_to.
"""
from django.test import Client, TestCase

from ..models.report import Report
from .factories import login, make_user


def make_report_for(name, available_for):
    return Report.objects.create(
        app='cis', name=name, title=name.replace('_', ' ').title(),
        description='', categories=['Students'], available_for=available_for,
    )


class ReportsInCategoryScopingTests(TestCase):
    def setUp(self):
        self.ce_only = make_report_for('ce_only_report', ['ce'])
        self.hs_report = make_report_for('hs_report', ['ce', 'highschool_admin'])
        self.instructor_report = make_report_for('instructor_report', ['instructor'])

    def _titles(self, user):
        result = Report.get_reports_in_category('Students', user)
        return {entry['title'] for entry in result['reports']}

    def test_a_student_sees_nothing(self):
        self.assertEqual(self._titles(make_user('stu', groups=('student',))), set())

    def test_an_instructor_sees_only_reports_published_to_instructors(self):
        self.assertEqual(
            self._titles(make_user('inst', groups=('instructor',))),
            {self.instructor_report.title},
        )

    def test_a_highschool_admin_sees_only_reports_published_to_them(self):
        self.assertEqual(
            self._titles(make_user('hs', groups=('highschool_admin',))),
            {self.hs_report.title},
        )

    def test_ce_staff_still_see_everything_in_the_category(self):
        self.assertEqual(
            self._titles(make_user('ce', groups=('ce',))),
            {self.ce_only.title, self.hs_report.title, self.instructor_report.title},
        )

    def test_the_endpoint_does_not_list_a_ce_only_report_to_a_student(self):
        client = Client()
        login(client, make_user('stu_http', groups=('student',)))
        resp = client.get('/ce/reports/reports_in_category/', {'category': 'Students'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['reports'], [])
