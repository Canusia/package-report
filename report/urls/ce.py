"""
    Support Ticket CE URL Configuration
"""
from django.urls import path, include

from rest_framework import routers

from report.views.report import (
    reports, reports_in_category,
    report_details, run_report,
    add_new as add_new_report,
    schedule_report,
    ReportSchedulerViewSet,
    run_command
)

app_name = 'report'

router = routers.DefaultRouter()
router_viewsets = {
    'report_scheduler': ReportSchedulerViewSet
}

for router_key in router_viewsets.keys():
    router.register(
        router_key,
        router_viewsets[router_key],
        basename=app_name
    )

urlpatterns = [

    path('api/', include(router.urls)),

    path('', reports, name='reports'),
    path('reports_in_category/', reports_in_category, name='reports_in_category'),
    path('report_details/', report_details, name='report_details'),
    path('run_report/<uuid:report_scheduler_id>', run_report, name='run_report'),
    path('run_command/<slug:command>', run_command, name='run_command'),

    path('schedule_report/', schedule_report, name='schedule_report'),
    path('add_new', add_new_report, name='add_new'),
]
