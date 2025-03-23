from django.test import TestCase
import logging

logger = logging.getLogger(__name__)

from django_tasks import task
from .models import Report, ReportScheduler

@task
def process_report(id):
    report = ReportScheduler.objects.get(pk=id)

    try:
        report.run()
    except Exception as e:
        logger.error(e)
        
        report.status = 'error'
        report.save()