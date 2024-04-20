import logging
from django.core.management import call_command
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

from report.models.report import Report, ReportScheduler

class Command(BaseCommand):
    '''
    Daily jobs
    '''
    help = ''

    def handle(self, *args, **kwargs):
        pending_reports = ReportScheduler.objects.filter(
            status__iexact='pending'
        )

        for report in pending_reports:
            try:
                report.run()
            except Exception as e:
                logger.error(e)
