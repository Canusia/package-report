# users/models.py
import os, uuid, datetime

from django.conf import settings
from django.http import HttpRequest
from django.db.models import JSONField
from django.urls import NoReverseMatch, reverse, reverse_lazy
from django.db import models, IntegrityError
from django.utils.module_loading import import_string

from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template import Context, Template
from django.template.loader import get_template, render_to_string

from mailer import send_mail, send_html_mail
from multiselectfield import MultiSelectField
from rest_framework import serializers

from cis.settings.reports_email import reports_email
from cis.utils import (
    user_has_cis_role, user_has_highschool_admin_role,
    user_has_instructor_role, getDomain
)
from cis.serializers.teacher import CustomUserSerializer

class ReportScheduler(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    created_on = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'cis.CustomUser',
        on_delete=models.PROTECT
    )

    report = models.ForeignKey(
        'report.Report',
        on_delete=models.PROTECT
    )

    data = JSONField(
        blank=True,
        null=True
    )

    ran_on = models.DateTimeField(blank=True, null=True)
    summary = JSONField(
        blank=True,
        null=True
    )

    status = models.CharField(
        choices=[
            ('pending', 'Pending'),
            ('ran', 'Ran'),
            ('error', 'Error'),
        ],
        max_length=20,
        default='pending'
    )

    @property
    def download_link(self):
        if self.status == 'ran':
            return 'download/' + str(self.id)
        return '-'

    @property
    def report_args(self):
        return self.data

    def run_report_link(self):
        return getDomain() + str(reverse_lazy('report:run_report', kwargs={
            'report_scheduler_id': self.id}))

    def _report_namespaces(self):
        """Namespaces to try when building a link this requester can open.

        `download_link` is a bare relative path (`download/<id>`) meant to be
        resolved against whichever `reports/` page it is rendered on, so it
        only works embedded in that page. An email has no such page to
        resolve against, so the link there needs an absolute URL, which means
        picking the right namespace first: 'report' is mounted at
        `ce/reports/` and 'highschool_admin_report' at
        `highschool_admin/reports/`. Mirrors
        Report.get_reports_in_category's precedence (CIS/CE staff can reach
        anything).

        A host need not mount both portals — umn's `myce/urls.py` includes
        `report.urls.ce` alone — so this is a preference order, not a single
        answer, and the caller falls back down it.
        """
        if not user_has_cis_role(self.created_by) and \
                user_has_highschool_admin_role(self.created_by):
            return ('highschool_admin_report', 'report')
        return ('report', 'highschool_admin_report')

    @property
    def download_email_link(self):
        """An absolute download URL, for use outside a `reports/` page.

        Falls back to the relative `download_link` rather than raising: this
        is reached from `email_requester()` at the end of `run()`, where a
        NoReverseMatch would lose the notification for a report that has
        already been generated.
        """
        for namespace in self._report_namespaces():
            try:
                return getDomain() + reverse(f'{namespace}:download', kwargs={
                    'report_scheduler_id': self.id})
            except NoReverseMatch:
                continue
        return self.download_link

    def email_requester(self):

        email_settings = reports_email.from_db()

        email = email_settings.get('email')
        subject = email_settings.get('subject')

        email_template = Template(email)
        context = Context({
            'first_name': self.created_by.first_name,
            'report_download_url': self.download_email_link,
            'report_title': self.report.title
        })

        text_body = email_template.render(context)
        to = [self.created_by.email]

        template = get_template('cis/email.html')
        html_body = template.render({
            'message': text_body
        })

        if getattr(settings, 'DEBUG', True):
            to = ['kadaji@gmail.com']

        send_html_mail(
            subject,
            text_body,
            html_body,
            settings.DEFAULT_FROM_EMAIL,
            to
        )
        return True

    def run(self):
        report_name = self.report.name
        reports_path = self.report.app + '.reports'
        report_class = import_string(
            f'{reports_path}.{report_name}.{report_name}'
        )

        report = report_class()
        path = report.run(self, self.data)

        self.status = 'ran'
        self.summary['download_link'] = path
        self.save()

        self.email_requester()

class ReportSchedulerSerializer(serializers.ModelSerializer):
    created_by = CustomUserSerializer()
    created_on = serializers.DateTimeField(format='%Y-%m-%d %I:%M %p')
    ran_on = serializers.DateTimeField(format='%Y-%m-%d %I:%M %p')
    download_link = serializers.CharField()
    report_title = serializers.SerializerMethodField()

    def get_report_title(self, obj):
        return obj.report.title if obj.report else ''

    class Meta:
        model = ReportScheduler
        fields = '__all__'

        datatables_always_serialize = [
            'id',
            'download_link',
            'status',
            'report_title',
        ]

class Report(models.Model):
    """
    Report model
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    app = models.CharField(max_length=100, default='cis')

    name = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=200, blank=True)
    
    STUDENTS = 'Students'
    HIGH_SCHOOLS = 'High Schools'
    CLASSES = 'Classes'
    MISC = 'Misc.'
    INSTRUCTORS = 'Instructors'

    CATEGORIES = [
        (STUDENTS, STUDENTS),
        (HIGH_SCHOOLS, HIGH_SCHOOLS),
        (CLASSES, CLASSES),
        (MISC, MISC),
        (INSTRUCTORS, INSTRUCTORS)
    ]
    categories = MultiSelectField(
        choices=CATEGORIES,
        max_choices=5,
        max_length=100
    )

    AVAILABLE_FOR = [
        ('ce', "EC Staff"),
        ('highschool_admin', 'High School Administrator'),
        ('instructor', 'Instructor'),
    ]
    available_for = MultiSelectField(
        choices=AVAILABLE_FOR
    )

    class Meta:
        unique_together = ['name', 'categories']

    def __str__(self):
        return self.name

    # The role each `available_for` choice names, and how to test for it.
    # Keyed by the AVAILABLE_FOR value so the two cannot drift apart.
    ROLE_TESTS = {
        'highschool_admin': user_has_highschool_admin_role,
        'instructor': user_has_instructor_role,
    }

    @classmethod
    def roles_of(cls, user):
        """Which AVAILABLE_FOR values `user` holds.

        Evaluated once and passed around rather than re-derived per report:
        each cis role helper calls `user.get_roles()`, which queries.
        """
        roles = {role for role, test in cls.ROLE_TESTS.items() if test(user)}
        if user_has_cis_role(user):
            roles.add('ce')
        return roles

    def available_to_roles(self, roles):
        """CE/CIS staff reach every report, matching the listing's
        long-standing precedence, so `available_for` is not consulted for
        them — a report published only to instructors still shows to CE.
        """
        if 'ce' in roles:
            return True
        return bool(roles & set(self.available_for))

    def is_available_to(self, user):
        """Whether `user` may load and run this report.

        `available_for` already records who a report is published to; it was
        only ever used to decide what to *list*, never to decide what a
        caller could actually run.
        """
        return self.available_to_roles(self.roles_of(user))

    @classmethod
    def get_reports_in_category(cls, category, user):
        reports = Report.objects.filter(
            categories__icontains=category
        )

        # No else here meant every other role — student, instructor,
        # faculty, tech center, applicant — got the unfiltered list with
        # `available_for` ignored entirely (#2 B5).
        roles = cls.roles_of(user)
        reports = [
            report for report in reports.order_by('title')
            if report.available_to_roles(roles)
        ]

        result = {
            'reports':[]
        }
        
        for report in reports:
            result['reports'].append({
                'id':report.id,
                'title':report.title
            })
        
        return result

