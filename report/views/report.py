import logging, json

from django.conf import settings
from django.db import IntegrityError
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
from django.http import JsonResponse

from crispy_forms.utils import render_crispy_form
from rest_framework import viewsets
from django.http import Http404, HttpResponseRedirect

from cis.models.settings import Setting
from cis.utils import user_has_cis_role

from cis.utils import (
    user_has_cis_role, user_has_highschool_admin_role,
    CIS_user_only,
    FACULTY_user_only,
    HSADMIN_user_only,
    INSTRUCTOR_user_only
)
from report.models.report import Report, ReportScheduler
from report.forms import AddReportForm
from report.models.report import ReportSchedulerSerializer

from cis.menu import cis_menu, draw_menu, HS_ADMIN_MENU

logger = logging.getLogger(__name__)

user_passes_test(user_has_cis_role, login_url='/')

class ReportSchedulerViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ReportSchedulerSerializer
    permission_classes = [CIS_user_only|FACULTY_user_only|HSADMIN_user_only|INSTRUCTOR_user_only]

    def get_queryset(self):
        report_id = self.request.GET.get('report_id')
        user_id = self.request.user.id

        return ReportScheduler.objects.filter(
            created_by__id=user_id,
            report__id=report_id
        )

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
    return HttpResponseRedirect(url)

def add_new(request):
    '''
    Add new page
    '''
    base_template = 'cis/logged-base.html'
    template = 'reports/add_new.html'
    ajax = request.GET.get('ajax', None)

    if request.method == 'POST':
        form = AddReportForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.save()

            messages.add_message(
                request,
                messages.SUCCESS,
                'Successfully added report',
                'list-group-item-success') 
            return redirect('report:add_new')
    else:
        form = AddReportForm()

    return render(
        request,
        template, {
            'form': form,
            'page_title': "Add New Report",
            'labels': {
                'all_items': 'All Reports'
            },
            'urls': {
                'add_new': 'cis:section_add_new',
                'all_items': 'report:reports'
            },
            'ajax': ajax,
            'base_template': base_template,
            'menu': draw_menu(cis_menu, 'reports', 'reports')
        })

def reports(request):
    template = 'reports/index.html'

    menu = {}
    intro = ''
    if user_has_cis_role(request.user):
        menu = draw_menu(cis_menu, 'reports', 'reports')
        categories = Report.CATEGORIES

    elif user_has_highschool_admin_role(request.user):
        from cis.settings.highschool_admin_portal import highschool_admin_portal as portal_lang

        intro = portal_lang(request).from_db().get("reports_blurb", 'Change me')
        menu = draw_menu(HS_ADMIN_MENU, 'reports', 'reports')
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

        report_html = render_to_string(
            'reports/report.html',
            {
                'form_html': form_html,
                'title': report.title,
                'description': report.description + f"<span class='text-white'>{report_name}</span>"
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

                return JsonResponse({
                    'message': 'Successfully scheduled report. You will get an email once the report has run',
                    'status': 'success'
                })
            else:
                # 'message': 'Please correct the errors and try again.',
                # 'details': mark_safe(str(teaching_formset.non_form_errors())),
                # 'errors': json.dumps(errors),
                # 'status': 'error'
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