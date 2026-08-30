"""
admin models
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from ..models.report import Report, ReportScheduler

class ReportAdmin(admin.ModelAdmin):
    model = Report

    list_display = [
        'title', 'name', 'app', 'categories_display', 'available_for_display',
    ]
    list_filter = ['app', 'categories', 'available_for']
    search_fields = ['title', 'name', 'description']
    ordering = ['title']

    @staticmethod
    def _labels(values, choices):
        lookup = dict(choices)
        return ', '.join(lookup.get(value, value) for value in values)

    @admin.display(description='Categories')
    def categories_display(self, obj):
        return self._labels(obj.get_categories_list(), Report.CATEGORIES)

    @admin.display(description='Available For')
    def available_for_display(self, obj):
        return self._labels(obj.get_available_for_list(), Report.AVAILABLE_FOR)

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