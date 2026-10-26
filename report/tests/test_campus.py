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
