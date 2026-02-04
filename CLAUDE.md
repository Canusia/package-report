# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Flexible, role-based reporting framework. Apps register reports via `REPORTS` configuration, which are dynamically loaded and executed. Supports scheduling, async processing, and S3 storage for generated files.

## Key Components

### Models (`models/report.py`)
- **Report** - Registry of available reports with categories and role access
- **ReportScheduler** - Scheduled/executed report instances with status tracking

### Report Categories
1. Students
2. High Schools
3. Classes
4. Misc.
5. Instructors

### Role Access
- `ce` - EC Staff
- `highschool_admin` - High School Administrator
- `instructor` - Instructor

## URL Structure
Available at `/ce/reports/`, `/faculty/reports/`, `/highschool_admin/reports/`:
- `reports_in_category/` - AJAX: Get reports by category
- `report_details/` - AJAX: Load report form
- `schedule_report/` - POST: Schedule execution
- `run_report/<uuid>` - Execute pending report
- `download/<uuid>` - Download completed report
- `api/report_scheduler/` - REST endpoint

## Commands

```bash
python manage.py register_reports  # Scan apps and register REPORTS
python manage.py run_reports       # Execute pending reports (cron job)
```

## Registering Reports

In your app's `apps.py` or `__init__.py`:
```python
REPORTS = [
    {
        'app': 'myapp',
        'name': 'MyReportClass',
        'title': 'My Report Title',
        'description': 'Description',
        'categories': ['Students', 'Classes'],
        'available_for': ['ce', 'highschool_admin']
    }
]
```

Report class location: `{app}.reports.{name}.{name}` with a `run(scheduler, data)` method.

## Report Execution Flow

1. User selects report and fills form
2. `schedule_report` creates ReportScheduler with status='pending'
3. `process_report` task enqueued via django-tasks
4. Task calls `ReportScheduler.run()`:
   - Dynamically imports report class
   - Calls `report.run(scheduler, data)`
   - Updates status to 'ran'
   - Stores download_link in summary
   - Emails requester

## Integration

- **Async Processing:** Uses `django-tasks` with 'reports' queue
- **Storage:** Reports saved to S3, downloaded via presigned URLs
- **Email:** Notification on completion via `mailer.send_html_mail()`
- **Permissions:** Filtered by user role, users see only their own scheduled reports
