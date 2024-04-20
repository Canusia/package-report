"""
admin models
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from ..models.report import Report, ReportScheduler

class ReportAdmin(admin.ModelAdmin):
    model = Report

class ReportSchedulerAdmin(admin.ModelAdmin):
    model = ReportScheduler
    list_display = [
        'created_on',
        'created_by',
        'report',
        'status',
        'data',
        'run_report_link',
        'download_link',
    ]
    
admin.site.register(ReportScheduler, ReportSchedulerAdmin)
admin.site.register(Report, ReportAdmin)