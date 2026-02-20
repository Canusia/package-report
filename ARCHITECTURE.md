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

Superusers can edit report title and description inline from the Description tab in the UI.

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

## Workflows

### 1. Report Generation Workflow

```
User → Reports Page → Select Category → Select Report → Fill Form → Generate Export
  → ReportScheduler created (status=pending)
  → process_report task enqueued (django-tasks)
  → db_worker picks up task
  → Report class dynamically imported: {app}.reports.{name}.{name}
  → report.run(task, data) executes
  → Output saved to S3 via PrivateMediaStorage
  → status=ran, download_link stored in summary
  → Email sent to requester
  → User downloads via presigned S3 URL
```

**Status transitions:** `pending` → `ran` (success) or `pending` → `error` (exception)

### 2. Smart Polling Workflow

The UI uses smart polling to provide near-instant feedback when reports complete:

1. **After scheduling:** frontend polls `status_check/` every 3 seconds
2. **Status change detected:** DataTable refreshes to show updated status and download link
3. **Backoff:** after ~5 minutes of fast polling, falls back to 60-second intervals
4. **No pending reports:** remains on 60-second slow poll
5. **Report switch:** clears existing poll timer, starts fresh

The `status_check/` endpoint is lightweight — returns only `id`, `status`, `download_link`, and a `has_pending` flag, avoiding full DRF serialization overhead.

### 3. Report Registration Workflow

```
Developer creates {app}/reports/{name}.py
  → Adds entry to AppConfig.REPORTS list
  → Runs: python manage.py register_reports
  → Report record created in database
  → Report appears in UI under configured categories
```

### 4. Superuser Report Editing Workflow

Superusers can edit report title and description directly from the UI:

1. Select a report → Description tab shows an **Edit** button
2. Click Edit → inline form with Title and Description fields
3. Save → AJAX POST to `update_report/` → updates Report model
4. UI updates the title in the header and sidebar without page reload

### 5. My Reports Workflow

The **My Reports** tab provides a consolidated view of all report runs for the current user across all report types:

1. User clicks "My Reports" tab on the reports page
2. DataTable loads from `api/report_scheduler/` (no report_id filter)
3. Shows: Date, Report Name, Status (with badges), Download link
4. Table refreshes each time the tab is activated

## Execution Flow

1. **User selects category** → AJAX GET to `reports_in_category/` returns matching reports filtered by role
2. **User selects report** → AJAX GET to `report_details/` dynamically imports `{app}.reports.{name}.{name}`, instantiates with `request`, renders crispy form
3. **User submits form** → POST to `schedule_report/` validates form, creates `ReportScheduler(status='pending')`, enqueues `process_report` task
4. **Smart polling begins** → frontend polls `status_check/` every 3 seconds
5. **Worker processes task** → `ReportScheduler.run()` dynamically imports report class, calls `report.run(task, data)`, report generates output and saves to S3 via `PrivateMediaStorage`
6. **Completion** → status set to `ran`, `summary.download_link` populated, requester emailed
7. **Frontend detects change** → DataTable refreshes, download link appears
8. **User downloads** → GET to `download/{id}` validates ownership, returns presigned S3 URL redirect

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
| `reports()` | GET | Main reports page with category sidebar and tabs |
| `reports_in_category()` | AJAX GET | Reports filtered by category and role |
| `report_details()` | AJAX GET | Dynamically rendered report form |
| `schedule_report()` | POST | Validate form, create scheduler, enqueue task |
| `report_status_check()` | AJAX GET | Lightweight status polling endpoint |
| `update_report()` | POST | Superuser: update report title/description |
| `run_report()` | GET | Manually execute a pending report |
| `download()` | GET | Presigned S3 URL for completed report |
| `run_command()` | GET | Execute management command (CE admin only) |
| `ReportSchedulerViewSet` | REST API | Report history for DataTables (filterable by report_id) |

## URL Routing

Three URL configs provide role-based access:

| Portal | Path | URL Config | Notes |
|--------|------|-----------|-------|
| CE (admin) | `/ce/reports/` | `report.urls.ce` | Full access including `run_command`, `update_report`, and REST API |
| Faculty | `/faculty/reports/` | `report.urls.faculty` | Standard access |
| HS Admin | `/highschool_admin/reports/` | `report.urls.highschool_admin` | Standard access |

## Templates

- **`index.html`** — Main UI with page-level tabs (Reports / My Reports), category sidebar, report list, form area, smart polling, and DataTables
- **`report.html`** — Report detail view with form, Description tab (editable for superusers), and Recent Runs tab
- **`base.html`** — Minimal bootstrap layout for standalone rendering

## File Structure

```
report/
├── report/
│   ├── models/
│   │   └── report.py          # Report, ReportScheduler, Serializer
│   ├── views/
│   │   └── report.py          # All view functions + ViewSet
│   ├── urls/
│   │   ├── ce.py              # CE admin routes
│   │   ├── faculty.py         # Faculty routes
│   │   └── highschool_admin.py
│   ├── templates/reports/
│   │   ├── index.html         # Main reports UI (tabs, polling, DataTables)
│   │   ├── report.html        # Report detail + form + inline edit
│   │   └── base.html
│   ├── management/commands/
│   │   ├── register_reports.py
│   │   └── run_reports.py
│   ├── admin.py
│   ├── apps.py                # ReportConfig / DevReportConfig
│   ├── forms.py               # AddReportForm
│   └── tasks.py               # process_report async task
├── ARCHITECTURE.md
├── PRODUCT_GUIDE.md
├── CLAUDE.md
├── README.rst
└── pyproject.toml
```

## Integration Points

Apps that currently register reports: `cis`, `pd_event`, `drop_wd`, `invoice`, `mou`, `django_grades`, `django_1098t`.

### Adding a New Report

1. Create `{app}/reports/{name}.py` with a `forms.Form` subclass named `{name}` that has a `run(self, task, data)` method
2. Add an entry to `REPORTS` in the app's `AppConfig`
3. Run `python manage.py register_reports`
