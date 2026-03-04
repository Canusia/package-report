"""
    Support Ticket CE URL Configuration
"""
from django.urls import path

from ..views.report import (
    reports, reports_in_category,
    report_details, run_report,
    add_new as add_new_report,
    report_status_check,
    schedule_report,
    download
)
app_name = 'highschool_admin_report'
urlpatterns = [
    path('', reports, name='reports'),
    path('reports_in_category/', reports_in_category, name='reports_in_category'),
    path('report_details/', report_details, name='report_details'),path('run_report/<uuid:report_scheduler_id>', run_report, name='run_report'),

    path('schedule_report/', schedule_report, name='schedule_report'),
    path('download/<uuid:report_scheduler_id>', download, name='download'),
    path('status_check/', report_status_check, name='report_status_check'),
    path('add_new', add_new_report, name='add_new'),
]
