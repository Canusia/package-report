"""
    Support Ticket CE URL Configuration
"""
from django.urls import path

from report.views.report import (
    reports, reports_in_category,
    report_details, run_report,
    add_new as add_new_report
)
app_name = 'highschool_admin_report'
urlpatterns = [
    path('', reports, name='reports'),
    path('reports_in_category/', reports_in_category, name='reports_in_category'),
    path('report_details/', report_details, name='report_details'),    path('run_report/<uuid:report_scheduler_id>', run_report, name='run_report'),

    path('add_new', add_new_report, name='add_new'),
]
