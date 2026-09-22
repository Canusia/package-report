"""`reports()` bound `categories` inside a CIS branch and an HS-admin branch
with no else, so the render at the bottom raised UnboundLocalError — a 500 —
for every other role: instructor, faculty, student, tech center, applicant.

Reported against a user who had an HSAdministrator record but was not in the
`highschool_admin` group, so neither branch ran.

The page may legitimately refuse these users (see the role checks on the CE
views), but it must not crash.
"""
from django.test import Client, TestCase

from .factories import login, make_user


class ReportsPageOtherRolesTests(TestCase):
    def _status(self, groups):
        client = Client()
        login(client, make_user('_'.join(groups) or 'no_role', groups=groups))
        return client.get('/ce/reports/').status_code

    def test_instructor_does_not_get_a_server_error(self):
        self.assertNotEqual(self._status(('instructor',)), 500)

    def test_student_does_not_get_a_server_error(self):
        self.assertNotEqual(self._status(('student',)), 500)

    def test_a_user_with_no_group_at_all_does_not_get_a_server_error(self):
        self.assertNotEqual(self._status(()), 500)
