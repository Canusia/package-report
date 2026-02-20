MyCE - Report
====================

Plugin-style reporting framework for Django. Provides report registration, scheduling,
async execution, and download infrastructure. Individual apps define their own reports
as Django form classes with a ``run()`` method.

Features
--------
- Dynamic report registration via ``AppConfig.REPORTS``
- Async execution via ``django-tasks`` (database backend)
- Smart polling UI with real-time status updates (3-second polling)
- Role-based access (CE, High School Admin, Faculty, Instructor)
- S3 storage with presigned URL downloads
- Email notifications on completion
- Superuser inline editing of report title/description
- "My Reports" tab showing all user report runs across report types

Installation
------------

In ``settings.py``, add the app to ``INSTALLED_APPS``::

    # Production
    'report.apps.ReportConfig'

    # Development (submodule)
    'report.report.apps.DevReportConfig'

Add static files path to ``STATICFILES_DIRS``::

    os.path.join(get_package_path("report"), 'staticfiles'),

In ``myce/urls.py``::

    path('ce/reports/', include('report.urls.ce')),
    path('faculty/reports/', include('report.urls.faculty')),
    path('highschool_admin/reports/', include('report.urls.highschool_admin')),

Run migrations::

    python manage.py migrate

Register reports from all apps::

    python manage.py register_reports

Adding a Report
---------------

1. Create ``{app}/reports/{name}.py``::

    from django import forms
    from crispy_forms.helper import FormHelper
    from crispy_forms.layout import Submit

    class my_report(forms.Form):
        # Define filter fields
        term = forms.ModelMultipleChoiceField(...)

        def __init__(self, request=None, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.helper = FormHelper()
            self.helper.add_input(Submit('submit', 'Generate Export'))

        def run(self, task, data):
            # task = ReportScheduler instance
            # data = submitted form data dict
            # Generate output, save to S3, return URL
            path = PrivateMediaStorage().save(path, ContentFile(...))
            return PrivateMediaStorage().url(path)

2. Add to your app's ``AppConfig``::

    class MyAppConfig(AppConfig):
        REPORTS = [
            {
                'app': 'myapp',
                'name': 'my_report',
                'title': 'My Report Title',
                'description': 'What this report does',
                'categories': ['Students'],
                'available_for': ['ce', 'highschool_admin']
            }
        ]

3. Run ``python manage.py register_reports``

Management Commands
-------------------

- ``register_reports`` — Scan apps and register report definitions in the database
- ``run_reports`` — Execute all pending reports (for cron fallback)

Dependencies
------------
- Django 4.2+
- django-tasks
- djangorestframework
- djangorestframework-datatables
- django-crispy-forms
- django-multiselectfield
- django-mailer
- boto3 (S3 storage)

Documentation
-------------
- ``ARCHITECTURE.md`` — Technical architecture and workflows
- ``PRODUCT_GUIDE.md`` — End-user product guide
