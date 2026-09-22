"""`schedule_report` and `report_details` resolved a report from a POSTed /
GETed id and acted on it with no role check at all — not that the caller is
CE, not that the report's `available_for` includes any role they hold.

`cis.middleware.LoginRequiredMiddleware` stops anonymous callers, so this is
an authenticated-user privilege escalation: a student or instructor account
could POST to /ce/reports/schedule_report/ with the id of, say, a detailed
student export and be emailed a CSV of student names, IDs, emails, high
schools, registrations and grades.

`available_for` is the existing expression of who a report is for; these
views now enforce it. CE/CIS staff keep access to everything, matching
Report.get_reports_in_category's own precedence.
"""
from django.test import Client, TestCase

from ..models.report import Report, ReportScheduler
from .factories import login, make_user

# A report class that actually imports, so a permitted caller gets past the
# authorization check into the real code path rather than a ModuleNotFoundError.
REAL_REPORT = {'app': 'cis', 'name': 'teacher_certificates'}


def make_real_report(available_for):
    return Report.objects.create(
        title='Teacher Certificates',
        description='',
        categories=['Instructors'],
        available_for=available_for,
        **REAL_REPORT,
    )


class ScheduleReportAuthorizationTests(TestCase):
    def _post(self, user, report):
        client = Client()
        login(client, user)
        return client.post(
            '/ce/reports/schedule_report/', {'report_id': str(report.id)})

    def test_a_student_cannot_schedule_a_ce_only_report(self):
        report = make_real_report(['ce'])
        resp = self._post(make_user('student_u', groups=('student',)), report)
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(ReportScheduler.objects.exists())

    def test_an_instructor_cannot_schedule_a_ce_only_report(self):
        report = make_real_report(['ce'])
        resp = self._post(make_user('instructor_u', groups=('instructor',)), report)
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(ReportScheduler.objects.exists())

    def test_a_highschool_admin_cannot_schedule_a_ce_only_report(self):
        report = make_real_report(['ce'])
        resp = self._post(make_user('hs_u', groups=('highschool_admin',)), report)
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(ReportScheduler.objects.exists())

    def test_a_highschool_admin_may_schedule_a_report_published_to_them(self):
        report = make_real_report(['ce', 'highschool_admin'])
        resp = self._post(make_user('hs_ok', groups=('highschool_admin',)), report)
        self.assertNotEqual(resp.status_code, 403)

    def test_an_instructor_may_schedule_a_report_published_to_them(self):
        report = make_real_report(['instructor'])
        resp = self._post(make_user('inst_ok', groups=('instructor',)), report)
        self.assertNotEqual(resp.status_code, 403)

    def test_ce_staff_may_schedule_a_report_not_published_to_them(self):
        report = make_real_report(['instructor'])
        resp = self._post(make_user('ce_u', groups=('ce',)), report)
        self.assertNotEqual(resp.status_code, 403)


class ReportDetailsAuthorizationTests(TestCase):
    def _get(self, user, report):
        client = Client()
        login(client, user)
        return client.get(
            '/ce/reports/report_details/', {'report_id': str(report.id)})

    def test_a_student_cannot_load_a_ce_only_report_form(self):
        report = make_real_report(['ce'])
        resp = self._get(make_user('student_d', groups=('student',)), report)
        self.assertEqual(resp.status_code, 403)

    def test_ce_staff_can_load_the_report_form(self):
        report = make_real_report(['ce'])
        resp = self._get(make_user('ce_d', groups=('ce',)), report)
        self.assertEqual(resp.status_code, 200)
