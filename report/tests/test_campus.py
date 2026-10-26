"""Scheduled reports remember the campus they were requested on and run
inside it (cis #129)."""
import uuid
from unittest import mock

from django.conf import settings
from django.test import TestCase, override_settings

from cis.campus_context import current_campus_or_none
from cis.models.course import Campus

from ..models.report import ReportScheduler


@override_settings(MULTI_CAMPUS=True)
class ReportCampusTests(TestCase):
    def setUp(self):
        self.campus = Campus.objects.create(
            name=f'C-{uuid.uuid4().hex[:6]}',
            code=f'{settings.CAMPUS_CODE_PREFIX}-{uuid.uuid4().hex[:6]}')

    def test_run_happens_inside_the_report_campus(self):
        scheduler = ReportScheduler(campus=self.campus)
        seen = {}
        with mock.patch.object(
                ReportScheduler, '_run',
                lambda self: seen.setdefault('campus', current_campus_or_none())):
            scheduler.run()
        self.assertEqual(seen['campus'], self.campus)

    def test_run_without_a_campus_sets_none(self):
        seen = {}
        with mock.patch.object(
                ReportScheduler, '_run',
                lambda self: seen.setdefault('campus', current_campus_or_none())):
            ReportScheduler().run()
        self.assertIsNone(seen['campus'])


@override_settings(MULTI_CAMPUS=True)
class ScheduleReportStampsCampusTests(TestCase):
    def test_schedule_view_saves_the_current_campus(self):
        from django.test import RequestFactory
        from cis.campus_context import campus_context
        from ..models.report import Report
        from ..views import report as report_views
        from .factories import make_user
        campus = Campus.objects.create(
            name=f'C-{uuid.uuid4().hex[:6]}',
            code=f'{settings.CAMPUS_CODE_PREFIX}-{uuid.uuid4().hex[:6]}')
        report = Report.objects.create(
            title='Teacher Certificates', description='', app='cis',
            name='teacher_certificates', categories=['Instructors'],
            available_for=['ce'])
        request = RequestFactory().post(
            '/ce/reports/schedule_report/', {'report_id': str(report.id)})
        request.user = make_user('ce_campus', groups=('ce',))
        with campus_context(campus), \
                mock.patch.object(report_views, 'process_report') as pr:
            resp = report_views.schedule_report(request)
        self.assertEqual(resp.status_code, 200, resp.content)
        pr.enqueue.assert_called_once()
        self.assertEqual(ReportScheduler.objects.get().campus, campus)
