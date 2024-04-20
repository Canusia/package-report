from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from django.conf import settings
from django.db.utils import IntegrityError

from report.models.report import Report
from django.utils.module_loading import import_string
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
        apps = getattr(settings, 'INSTALLED_APPS')
        for app in apps:
            try:
                app_class = import_string(app)
                if app_class.REPORTS:
                    print(f'Found Reports in {app}')
                    self.register(app_class.REPORTS)
            except:
                ...
