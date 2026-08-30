"""
admin models
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count

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

    def _run_counts(self, report):
        """All-time run counts for *report*, one row per requesting user,
        split by status and ordered by total descending."""
        rows = {}
        aggregate = (
            ReportScheduler.objects
            .filter(report=report)
            .values(
                'created_by__id',
                'created_by__first_name',
                'created_by__last_name',
                'created_by__email',
                'status',
            )
            .annotate(n=Count('id'))
        )
        for row in aggregate:
            key = row['created_by__id']
            entry = rows.setdefault(key, {
                'name': f"{row['created_by__first_name']} "
                        f"{row['created_by__last_name']}".strip(),
                'email': row['created_by__email'],
                'pending': 0, 'ran': 0, 'error': 0, 'total': 0,
            })
            status = row['status']
            if status in entry:
                entry[status] = row['n']
            entry['total'] += row['n']
        return sorted(rows.values(), key=lambda r: r['total'], reverse=True)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        report = self.get_object(request, object_id)
        extra_context['run_counts'] = (
            self._run_counts(report) if report else [])
        return super().change_view(
            request, object_id, form_url, extra_context=extra_context)

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