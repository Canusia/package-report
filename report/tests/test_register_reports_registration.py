"""`register()` wrapped `db_record.save()` in `except Exception: ...`, so a
report that failed to register did so silently — no output, no row, exit 0.

Registration stays insert-only by design: once a Report row exists, superusers
own title/description/categories/available_for through the Description tab and
the admin, and those edits are meant to outlive the app's declared REPORTS
manifest. See CLAUDE.md, "Registering Reports".
"""
from io import StringIO

from django.test import TestCase

from ..management.commands.register_reports import Command
from ..models.report import Report


def manifest(name, **overrides):
    record = {
        'app': 'cis', 'name': name, 'title': f'{name} title',
        'description': 'D', 'categories': ['Students'], 'available_for': ['ce'],
    }
    record.update(overrides)
    return record


class RegisterTests(TestCase):
    def register(self, records):
        command = Command(stdout=StringIO(), stderr=StringIO())
        command.register(records)
        return command.stdout.getvalue(), command.stderr.getvalue()

    def test_a_new_report_is_created(self):
        self.register([manifest('brand_new')])
        self.assertTrue(Report.objects.filter(name='brand_new').exists())

    def test_an_existing_report_is_left_untouched(self):
        Report.objects.create(
            app='cis', name='existing', title='Curated title',
            description='Curated description', categories=['Classes'],
            available_for=['ce', 'highschool_admin'],
        )

        self.register([manifest(
            'existing', title='Manifest title', description='Manifest description',
            categories=['Students'], available_for=['ce'],
        )])

        report = Report.objects.get(name='existing')
        self.assertEqual(report.title, 'Curated title')
        self.assertEqual(report.description, 'Curated description')
        self.assertEqual(list(report.categories), ['Classes'])
        self.assertEqual(list(report.available_for), ['ce', 'highschool_admin'])

    def test_a_malformed_record_is_reported_not_swallowed(self):
        broken = manifest('broken')
        del broken['title']

        _, errors = self.register([broken])

        self.assertIn('broken', errors)
        self.assertFalse(Report.objects.filter(name='broken').exists())

    def test_a_malformed_record_does_not_stop_the_ones_after_it(self):
        broken = manifest('broken')
        del broken['title']

        self.register([broken, manifest('still_registered')])

        self.assertTrue(Report.objects.filter(name='still_registered').exists())
