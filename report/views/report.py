import logging, json
from urllib.parse import urlparse

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test, login_required
from django.utils.module_loading import import_string
from django.http import Http404
from django.utils.safestring import mark_safe

from django.template.context_processors import csrf
from django.template.loader import render_to_string

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import get_object_or_404, redirect, render

from crispy_forms.utils import render_crispy_form
from rest_framework import viewsets
from django.http import Http404, HttpResponseRedirect, HttpResponse

from cis.models.settings import Setting
from cis.utils import user_has_cis_role

from cis.utils import get_s3_url

from cis.utils import (
    user_has_cis_role, user_has_highschool_admin_role,
    CIS_user_only,
    FACULTY_user_only,
    HSADMIN_user_only,
    INSTRUCTOR_user_only
)

from ..models.report import Report, ReportScheduler
from ..forms import AddReportForm
from ..models.report import ReportSchedulerSerializer

from ..tasks import process_report

from cis.menu import cis_menu, draw_menu, HS_ADMIN_MENU

logger = logging.getLogger(__name__)

user_passes_test(user_has_cis_role, login_url='/')

def extract_bucket_key(s3_url):
    parsed = urlparse(s3_url)
    bucket = parsed.netloc.split('.')[0]
    key = parsed.path.lstrip('/')
    return bucket, key

class ReportSchedulerViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ReportSchedulerSerializer
    permission_classes = [CIS_user_only|FACULTY_user_only|HSADMIN_user_only|INSTRUCTOR_user_only]

    def get_queryset(self):
        report_id = self.request.GET.get('report_id')
        user_id = self.request.user.id

        qs = ReportScheduler.objects.filter(created_by__id=user_id)
        if report_id:
            qs = qs.filter(report__id=report_id)
        return qs.select_related('report')

def run_command(request, command):

    from django.core.management import call_command
    
    try:
        call_command(command)

        return JsonResponse({
            'message': 'Successfully ran command',
            'status': 'success'
        })
    except Exception as e:
        logger.error(e)

        return JsonResponse({
            'message': 'failed to run command',
            'error': e,
            'status': 'success'
        })

def download(request, report_scheduler_id):
    report = get_object_or_404(ReportScheduler, pk=report_scheduler_id)

    if report.status != 'ran':
        return Http404("Report is not ready for download")
    
    if report.created_by != request.user:
        return Http404("You did not generate this report")
    
    url = report.summary.get('download_link')
    s3, key = extract_bucket_key(url)
    
    url = get_s3_url(key)

    return HttpResponseRedirect(url)

@login_required(login_url='/')
def report_status_check(request):
    report_id = request.GET.get('report_id')
    if not report_id:
        return JsonResponse({'reports': [], 'has_pending': False})

    schedulers = ReportScheduler.objects.filter(
        created_by=request.user,
        report__id=report_id
    ).order_by('-created_on')[:20]

    reports = []
    for s in schedulers:
        download = '-'
        if s.status == 'ran' and s.summary:
            download = 'download/' + str(s.id)
        reports.append({
            'id': str(s.id),
            'status': s.status,
            'download_link': download,
        })

    has_pending = any(r['status'] == 'pending' for r in reports)

    return JsonResponse({
        'reports': reports,
        'has_pending': has_pending,
    })


def add_new(request):
    ...

def reports(request):
    template = 'reports/index.html'

    menu = {}
    intro = ''
    if user_has_cis_role(request.user):
        menu = draw_menu(cis_menu, 'reports', 'reports', 'ce')
        categories = Report.CATEGORIES

    elif user_has_highschool_admin_role(request.user):
        from cis.settings.highschool_admin_portal import highschool_admin_portal as portal_lang

        intro = portal_lang(request).from_db().get("reports_blurb", 'Change me')
        menu = draw_menu(HS_ADMIN_MENU, 'reports', 'reports', 'highschool_admin')
        categories = [
            (Report.CLASSES, Report.CLASSES),
            (Report.STUDENTS, Report.STUDENTS),
            (Report.MISC, Report.MISC)
        ]

    return render(
        request,
        template, {
            'categories': categories,
            'intro': intro,
            'menu': menu
        })
    
@login_required(login_url='/')
def reports_in_category(request):
    category = request.GET.get('category', None)
    if category:
        reports_available = Report.get_reports_in_category(category, request.user)
    else:
        reports_available = {}
    return JsonResponse(reports_available)

def report_details(request, report_id=None):
    if not report_id:
        report_id = request.GET.get('report_id', None)

    report = get_object_or_404(Report, pk=report_id)    
    report_name = report.name

    try:
        reports_path = report.app + '.reports'
        report_class = import_string(
            f'{reports_path}.{report_name}.{report_name}'
        )

        form = report_class(request)
        ctx = {}
        ctx.update(csrf(request))
        form_html = render_crispy_form(form, context=ctx)

        # "Use as datasource" hands off to the announcement bulk-mailer, which
        # only has the handoff endpoint in newer versions. Gated behind a
        # default-off flag so the button never shows unless a deployment whose
        # announcement supports it opts in (settings.REPORTS_USE_AS_DATASOURCE_ENABLED = True).
        use_as_datasource = (
            bool(getattr(report_class, 'use_as_datasource', False))
            and bool(getattr(settings, 'REPORTS_USE_AS_DATASOURCE_ENABLED', False))
        )

        report_html = render_to_string(
            'reports/report.html',
            {
                'form_html': form_html,
                'title': report.title,
                'description': report.description + f"<span class='text-white'>{report_name}</span>",
                'raw_description': report.description,
                'is_superuser': request.user.is_superuser,
                'report_id': str(report.id),
                'use_as_datasource': use_as_datasource,
                'all_categories': Report.CATEGORIES,
                'all_available_for': Report.AVAILABLE_FOR,
                'selected_categories': list(report.categories),
                'selected_available_for': list(report.available_for),
            }
        )
        data = {
            'status':'success',
            'report':report_html,
        }
    except ModuleNotFoundError as e:
        logger.error(e)
        data = {
            'status': 'error',
            'message': 'Unable to locate report, ' + str(e)
        }
    except AttributeError as e:
        logger.error(e)
        data = {
            'status': 'error',
            'message': 'Unable to get report details ' + str(e)
        }
    return JsonResponse(data)


def schedule_report(request):
    if request.method == 'POST':
        
        report = get_object_or_404(Report, pk=request.POST.get('report_id'))
        report_name = report.name

        try:
            reports_path = report.app + '.reports'
        
            report_class = import_string(f'{reports_path}.{report_name}.{report_name}')

            form = report_class(request, request.POST)
            if form.is_valid():
                report_scheduler = ReportScheduler(
                    created_by=request.user,
                    report=report,
                    data=dict(request.POST),
                    summary={}
                )
                report_scheduler.save()

                task_id = process_report.enqueue(str(report_scheduler.id))

                return JsonResponse({
                    'message': 'Successfully scheduled report. You will get an email once the report has run',
                    'status': 'success',
                    'report_scheduler_id': str(report_scheduler.id),
                })
            else:
                return JsonResponse({
                    'message': 'Please correct the following errors and try again.',
                    'details': mark_safe(str(form.errors)),
                    'status': 'error',
                    'errors': form.errors.as_json()
                }, status=400)
        except Exception as e:
            logger.error(e)
            return JsonResponse({
                'message': 'Please correct the following errors and try again.',
                'details': 'Exception - ' + str(e)
            }, status=400)


@login_required(login_url='/')
def update_report(request):
    if not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=405)

    report_id = request.POST.get('report_id')
    report = get_object_or_404(Report, pk=report_id)

    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()

    if not title:
        return JsonResponse({'status': 'error', 'message': 'Title is required'}, status=400)

    categories = request.POST.getlist('categories')
    available_for = request.POST.getlist('available_for')

    valid_categories = {value for value, _ in Report.CATEGORIES}
    valid_roles = {value for value, _ in Report.AVAILABLE_FOR}

    if not categories:
        return JsonResponse({
            'status': 'error',
            'message': 'Select at least one category.'}, status=400)
    if not set(categories).issubset(valid_categories):
        return JsonResponse({
            'status': 'error',
            'message': 'Unrecognised category submitted.'}, status=400)

    if not available_for:
        return JsonResponse({
            'status': 'error',
            'message': 'Select at least one role.'}, status=400)
    if not set(available_for).issubset(valid_roles):
        return JsonResponse({
            'status': 'error',
            'message': 'Unrecognised role submitted.'}, status=400)

    report.title = title
    report.description = description
    report.categories = categories
    report.available_for = available_for

    try:
        # Savepoint: without it the IntegrityError poisons the surrounding
        # transaction and the next query (the session write in
        # SessionMiddleware) raises TransactionManagementError.
        with transaction.atomic():
            report.save()
    except IntegrityError:
        # Report.Meta.unique_together = ['name', 'categories']
        return JsonResponse({
            'status': 'error',
            'message': (f'A report named {report.name} already exists with '
                        'those categories.'),
        }, status=400)

    return JsonResponse({
        'status': 'success',
        'message': ('Report updated successfully. Category changes appear in '
                    'the left-hand list after the next page load.'),
        'title': report.title,
        'description': report.description,
        'categories': list(report.categories),
        'available_for': list(report.available_for),
    })


def run_report(request, report_scheduler_id):
    scheduled_report = ReportScheduler.objects.get(
        pk=report_scheduler_id
    )

    try:
        scheduled_report.run()

        return JsonResponse({
            'message': 'Successfully ran report',
            'status': 'success'
        })
    except Exception as e:
        logger.error(e)

        return JsonResponse({
            'message': 'failed to run report',
            'error': e,
            'status': 'success'
        })