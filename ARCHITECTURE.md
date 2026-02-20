# Report Module Architecture

## Overview

The report module is a plugin-style reporting framework for Django. It provides infrastructure (models, views, templates, task queue integration) while individual apps supply report definitions. Any app can register reports without importing from or depending on this package.

## Models

### Report

Registry entry for a report definition.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUIDField (PK) | Primary key |
| `app` | CharField | Source app (e.g. `cis`, `pd_event`) |
| `name` | CharField | Report class name, matches module/class |
| `title` | CharField | User-facing display title |
| `description` | CharField | Brief description |
| `categories` | MultiSelectField | One or more of: Students, High Schools, Classes, Misc., Instructors |
| `available_for` | MultiSelectField | Role access: `ce`, `highschool_admin`, `instructor` |

Key method: `get_reports_in_category(category, user)` filters reports by category and user role.

### ReportScheduler

Tracks each report execution.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUIDField (PK) | Primary key |
| `created_on` | DateTimeField | When scheduled |
| `created_by` | FK → CustomUser | Requesting user |
| `report` | FK → Report | Which report |
| `data` | JSONField | Submitted form data |
| `status` | CharField | `pending`, `ran`, or `error` |
| `ran_on` | DateTimeField | When executed |
| `summary` | JSONField | Contains `download_link` after execution |

Key methods:
- `run()` — dynamically imports and executes the report class, updates status, emails requester
- `email_requester()` — sends completion notification via django-mailer

## Report Definition Pattern

Each report is a Django `forms.Form` subclass with a `run()` method. Reports live at `{app}/reports/{name}.py` and the class name matches the file name.

```python
# cis/reports/class_roster.py
class class_roster(forms.Form):
    term = forms.ModelMultipleChoiceField(...)

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit('submit', 'Generate Export'))

    def run(self, task, data):
        # task = ReportScheduler instance
        # data = submitted form data dict
        # Generate CSV/Excel, save to S3, return URL
        path = PrivateMediaStorage().save(path, ContentFile(...))
        return PrivateMediaStorage().url(path)
```

There is no base class — reports are plain forms with a `run()` method. This means apps have zero import dependency on the report package.

## Registration

### App Configuration

Apps declare reports in their `AppConfig.REPORTS` list:

```python
class CisConfig(AppConfig):
    REPORTS = [
        {
            'app': 'cis',
            'name': 'class_roster',
            'title': 'Class Roster Export',
            'description': 'Export class roster data',
            'categories': ['Classes'],
            'available_for': ['ce', 'highschool_admin']
        },
        # ...
    ]
```

### Management Command

`python manage.py register_reports` scans all `INSTALLED_APPS` for a `REPORTS` attribute on the AppConfig and creates corresponding `Report` database entries.

## Execution Flow

1. **User selects category** → AJAX GET to `reports_in_category/` returns matching reports filtered by role
2. **User selects report** → AJAX GET to `report_details/` dynamically imports `{app}.reports.{name}.{name}`, instantiates with `request`, renders crispy form
3. **User submits form** → POST to `schedule_report/` validates form, creates `ReportScheduler(status='pending')`, enqueues `process_report` task
4. **Worker processes task** → `ReportScheduler.run()` dynamically imports report class, calls `report.run(task, data)`, report generates output and saves to S3 via `PrivateMediaStorage`
5. **Completion** → status set to `ran`, `summary.download_link` populated, requester emailed
6. **User downloads** → GET to `download/{id}` validates ownership, returns presigned S3 URL redirect

```
User → [Select Category] → AJAX → [Select Report] → AJAX → [Submit Form]
  → POST → ReportScheduler(pending) → django-tasks queue
  → db_worker → ReportScheduler.run() → {app}.reports.{name}.{name}.run()
  → S3 upload → status=ran → email notification → User downloads
```

## Task Queue

Uses `django-tasks` with database backend (not Celery).

```python
# tasks.py
@task
def process_report(id):
    report = ReportScheduler.objects.get(pk=id)
    try:
        report.run()
    except Exception as e:
        report.status = 'error'
        report.save()
```

Fallback: `python manage.py run_reports` batch-executes all pending reports (for cron).

## Views

| View | Method | Purpose |
|------|--------|---------|
| `reports()` | GET | Main reports page with category sidebar |
| `reports_in_category()` | AJAX GET | Reports filtered by category and role |
| `report_details()` | AJAX GET | Dynamically rendered report form |
| `schedule_report()` | POST | Validate form, create scheduler, enqueue task |
| `run_report()` | GET | Manually execute a pending report |
| `download()` | GET | Presigned S3 URL for completed report |
| `run_command()` | GET | Execute management command (CE admin only) |
| `ReportSchedulerViewSet` | REST API | Read-only report history for DataTables |

## URL Routing

Three URL configs provide role-based access:

| Portal | Path | URL Config | Notes |
|--------|------|-----------|-------|
| CE (admin) | `/ce/reports/` | `report.urls.ce` | Full access including `run_command` and REST API |
| Faculty | `/faculty/reports/` | `report.urls.faculty` | Standard access |
| HS Admin | `/highschool_admin/reports/` | `report.urls.highschool_admin` | Standard access |

## Templates

- **`index.html`** — Main UI with category sidebar, report list, form area, and DataTables execution history (auto-refreshes every 60s)
- **`report.html`** — Report detail view with form and recent runs tabs
- **`base.html`** — Minimal bootstrap layout for standalone rendering

## File Structure

```
report/
├── report/
│   ├── models/
│   │   └── report.py          # Report, ReportScheduler
│   ├── views/
│   │   └── report.py          # All view functions + ViewSet
│   ├── urls/
│   │   ├── ce.py              # CE admin routes
│   │   ├── faculty.py         # Faculty routes
│   │   └── highschool_admin.py
│   ├── templates/reports/
│   │   ├── index.html         # Main reports UI
│   │   ├── report.html        # Report detail + form
│   │   └── base.html
│   ├── management/commands/
│   │   ├── register_reports.py
│   │   └── run_reports.py
│   ├── admin.py
│   ├── apps.py                # ReportConfig / DevReportConfig
│   ├── forms.py               # AddReportForm
│   └── tasks.py               # process_report async task
├── ARCHITECTURE.md
├── CLAUDE.md
└── pyproject.toml
```

## Integration Points

Apps that currently register reports: `cis`, `pd_event`, `drop_wd`, `invoice`, `mou`, `django_grades`, `django_1098t`.

### Adding a New Report

1. Create `{app}/reports/{name}.py` with a `forms.Form` subclass named `{name}` that has a `run(self, task, data)` method
2. Add an entry to `REPORTS` in the app's `AppConfig`
3. Run `python manage.py register_reports`
