from django.apps import apps as django_apps
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from django.conf import settings
from django.db.utils import IntegrityError

from ...models.report import Report


def discover_manifests(app_configs):
    """Yield (app label, REPORTS) for every app declaring reports.

    Walks the app registry rather than resolving INSTALLED_APPS strings with
    `import_string()`: that only works when the entry is the dotted path to
    the AppConfig class, so a plain entry ('student', 'instructor', ...)
    raised and was swallowed, and those apps' reports never registered.

    README and CLAUDE.md both document declaring REPORTS "in your app's
    `apps.py` or `__init__.py`", so both placements are accepted, the
    AppConfig winning if an app somehow has both.
    """
    for config in app_configs:
        reports = getattr(config, 'REPORTS', None)
        if not reports:
            reports = getattr(config.module, 'REPORTS', None)
        if reports:
            yield config.name, reports


class Command(BaseCommand):
    '''
    Register reports in DB

    AVAILABLE_FOR = [
        ('ce', "EC Staff"),
        ('highschool_admin', 'High School Administrator'),
        ('instructor', 'Instructor'),
        ('tech_center', "Tech. Center Staff"),
    ]
    '''
    help = 'Register reports in DB'

    def register(self, reports):

        for record in reports:
            if not Report.objects.filter(name=record['name']).exists():
                db_record = Report(
                    app=record.get('app', 'cis'),
                    name=record['name'],
                    title=record['title'],
                    description=record['description'],
                    categories=record['categories'],
                    available_for=record['available_for']
                )
                
                try:
                    db_record.save()
                    print(f'Added {record["name"]}')
                except Exception as e:
                    ...
            else:
                print(f'Report - {record["name"]} exists')

    def handle(self, *args, **kwargs):
        for app_name, reports in discover_manifests(django_apps.get_app_configs()):
            self.stdout.write(f'Found {len(reports)} report(s) in {app_name}')
            self.register(reports)
