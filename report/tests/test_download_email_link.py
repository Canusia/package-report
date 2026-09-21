"""The "report ready" email's download link was the bare relative string
`download_link` produces ('download/<id>'), meant only to be resolved against
whichever `reports/` page renders it (see `templates/reports/index.html`). An
email has no such page, so the link never resolved for the requester at all.

`download_email_link()` builds an absolute URL instead, picking the namespace
('report' at ce/reports/, or 'highschool_admin_report' at
highschool_admin/reports/) that matches the requester's portal — a High
School Administrator's email must not point at the CE-only mount.
"""
from django.test import TestCase
from django.urls import reverse

from cis.utils import getDomain

from .factories import make_report, make_scheduler, make_user


class DownloadEmailLinkTests(TestCase):
    def test_ce_requester_gets_an_absolute_ce_download_link(self):
        scheduler = make_scheduler(
            make_report(), make_user('ce_requester', groups=('ce',)), status='ran')
        expected = getDomain() + reverse(
            'report:download', kwargs={'report_scheduler_id': scheduler.id})
        self.assertEqual(scheduler.download_email_link(), expected)

    def test_highschool_admin_requester_gets_the_highschool_admin_namespace(self):
        scheduler = make_scheduler(
            make_report(),
            make_user('hs_admin_requester', groups=('highschool_admin',)),
            status='ran',
        )
        expected = getDomain() + reverse(
            'highschool_admin_report:download', kwargs={'report_scheduler_id': scheduler.id})
        self.assertEqual(scheduler.download_email_link(), expected)

    def test_a_user_in_both_roles_gets_the_ce_namespace(self):
        """Matches Report.get_reports_in_category's own precedence: CIS/CE
        staff can reach anything, so they get the CE-mounted link."""
        scheduler = make_scheduler(
            make_report(),
            make_user('both_roles', groups=('ce', 'highschool_admin')),
            status='ran',
        )
        expected = getDomain() + reverse(
            'report:download', kwargs={'report_scheduler_id': scheduler.id})
        self.assertEqual(scheduler.download_email_link(), expected)

    def test_it_is_not_the_bare_relative_download_link(self):
        scheduler = make_scheduler(
            make_report(), make_user('ce_requester2', groups=('ce',)), status='ran')
        self.assertNotEqual(scheduler.download_email_link(), scheduler.download_link)
        self.assertIn(scheduler.download_link, scheduler.download_email_link())
