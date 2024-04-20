"""
admin models
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from ..models.report import Report, ReportScheduler

# Register your models here.
@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'title', 'categories', 'available_for'
    )
    fields = [
        'name',
        'title',
        'description',
        'categories',
        'available_for'
    ]


@admin.register(ReportScheduler)
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