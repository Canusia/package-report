from django.test import TestCase
from django.utils import timezone

from ..models.report import ReportScheduler
from .factories import make_report, make_scheduler, make_user


class FactoryTests(TestCase):
    def test_make_scheduler_backdates_created_on(self):
        report = make_report()
        user = make_user('ce1')
        scheduler = make_scheduler(report, user, days_ago=40)
        age = (timezone.now() - scheduler.created_on).days
        self.assertGreaterEqual(age, 39)

    def test_superuser_factory_sets_flag(self):
        self.assertTrue(make_user('root', superuser=True).is_superuser)

    def test_make_scheduler_defaults_to_pending(self):
        scheduler = make_scheduler(make_report(), make_user('ce2'))
        self.assertEqual(
            ReportScheduler.objects.get(pk=scheduler.pk).status, 'pending')
