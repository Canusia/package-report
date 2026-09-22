# Changelog

All notable changes to `myce_report` (the MyCE reporting framework).

Releases are git-tag-driven on `Canusia/package-report`; each tenant pins a tag through the
`git+https://…@<tag>` line in its `webapp/requirements.txt`. The package's `version` in
`setup.cfg` and `pyproject.toml` always declares the tag it was cut at — pip keys upgrades
off the version string, not the tag, so a frozen version makes an incremental install
silently keep the old code.

## v2026.2.2 — 2026-09-22

Addresses `Canusia/package-report#2`, reported against v2026.1.1 while publishing grade
reports to the HS admin portal. **No model changes, so no migrations.**

The issue's headline blocker (A1, the HS admin URLconf not registering the DRF router, so
a school admin could submit a report but never reach the download link) was already fixed
in **v2026.1.2**, and its `run_command` / `run_report` items (B3, B4) in **v2026.2.1**.
Anyone still on v2026.1.1 gets those by upgrading.

### Security
- **`available_for` is now an authorization check, not just a listing filter.**
  `schedule_report` resolved a report from a POSTed `report_id` and enqueued a run of it
  with no check that the caller is CE, nor that the report was published to any role they
  hold; `report_details` had the same gap on the form-loading side. `LoginRequiredMiddleware`
  stops anonymous callers, so this was an authenticated-user privilege escalation —
  verified in test that a user in the `student` group POSTing a `available_for=['ce']`
  report received a 200 and a persisted `ReportScheduler`, which for a typical deployment
  means being emailed a CSV of student names, IDs, emails, high schools, registrations and
  grades. Both views now answer to `Report.is_available_to()`, and both gain the
  `@login_required` they read as having.

- **`Report.get_reports_in_category` scoped to every role.** It filtered on `available_for`
  for HS admins and deliberately skipped the filter for CIS/CE, but had no `else` — so a
  student, instructor, faculty or tech-center user received every report in the category
  with `available_for` ignored entirely. `reports_in_category` is only `@login_required`,
  so that listing was reachable, and the gap above made each listed report runnable.

  CE behaviour is unchanged on purpose: CE staff still see reports not published to them.
  The `('instructor', 'Instructor')` choice in `AVAILABLE_FOR` had no branch anywhere and
  did nothing; it now selects reports. Roles are resolved once per call rather than per
  report, because each `cis` role helper calls `user.get_roles()`, which queries.

### Fixed
- **The report-ready email's download link never resolved.** `ReportScheduler.download_link`
  is a bare relative path (`download/<id>`) meant to be resolved against whichever
  `reports/` page renders it; an email has no such page. `download_email_link` builds an
  absolute URL against the requester's own portal. It falls back rather than raising when
  a host mounts only one portal — umn's `myce/urls.py` includes `report.urls.ce` alone, so
  reversing `highschool_admin_report:download` there raised `NoReverseMatch` out of
  `email_requester()`, *after* `run()` had already generated and saved the report, losing
  the notification for a run that had succeeded. `download_link` itself is unchanged: it is
  still correct for the DataTables row link and the admin changelist. (PR #1, thanks
  @ndHammer.)

- **`templates/reports/index.html` addresses the portal it is served from.** The template
  serves the CE, HS admin and faculty portals, but its three AJAX endpoints were hardcoded
  to the CE namespace, so a school admin on `/highschool_admin/reports/` sent their category
  lookups, report-form loads and submissions to `/ce/reports/`. That worked only because
  those CE views carried no role check, and it left the HS admin portal's own routes
  unexercised — so their absence would have been invisible. The analytics block's `report:`
  URLs are deliberately left alone: `run_summary`, `bulk_actions` and `all_report_scheduler`
  are CE-only endpoints.

- **`reports()` no longer 500s for roles with no branch.** `categories` was bound only inside
  the CIS and HS-admin branches, so the render raised `UnboundLocalError` for instructors,
  faculty, students, tech-center users and applicants. Hit in practice by a user who had an
  `HSAdministrator` record but was not in the `highschool_admin` group, so neither branch ran.

- **`register_reports` no longer swallows registration failures.** The save sat in
  `except Exception: ...`, so a report that failed to register produced no output, no row
  and exit 0. Failures are now named on stderr and registration continues — one malformed
  manifest must not cost the other apps their reports.

### Changed
- **`register_reports` discovers apps through the app registry.** It called `import_string()`
  on each `INSTALLED_APPS` entry, which only resolves when the entry is the dotted path to
  the AppConfig class; a plain entry (`'student'`, `'instructor'`, …) raised and a bare
  `except:` swallowed it, so those apps' reports never registered and nothing said so.
  Discovery now walks `apps.get_app_configs()` and accepts `REPORTS` on either the AppConfig
  or the app module, as README and CLAUDE.md both document.

- **`download_email_link` is a property**, matching `download_link` and `report_args`
  beside it.

### Deliberately not changed
- **`register_reports` remains insert-only.** The issue asked for an upsert on `name`, so
  that publishing an existing report to a new role would be a code change rather than a
  per-tenant data migration. Declined: superusers own `title`, `description`, `categories`
  and `available_for` through the Description tab and the admin, and those edits are meant
  to outlive the app's declared `REPORTS`. An upsert would clobber every tenant's
  customisation on the next deploy run. The documented contract stands — once a report is
  registered, the database row, not the `REPORTS` list, is the source of truth. There is
  now a test pinning it.

## v2026.2.1 — 2026-08-30

### Security
- **`run_command` is superuser-only.** `/ce/reports/run_command/<slug:command>`
  executes a Django management command by name and shipped with no role check at all.
  `cis.middleware.LoginRequiredMiddleware` enforces login but not any role, so every
  authenticated user — verified against a user in the `student` group — could execute
  any no-argument management command in the deployment, including the SIS importers and
  the cron-job commands. The view is not referenced by any template or JS. It now
  requires `is_superuser`.

  A bare `user_passes_test(user_has_cis_role, login_url='/')` statement sat at module
  scope in `views/report.py`, its return value discarded. It decorated nothing and
  protected nothing, while reading as though the module were guarded; removed.

- **`run_report/<uuid>` is superuser-only.** Same gap: any authenticated user could
  trigger any queued report to execute synchronously, which also emails that row's
  requester. Its only caller is the `run_report_link` column on the `ReportScheduler`
  admin changelist. The gate is deliberately *not* scoped to the row's owner — a
  superuser may run any scheduled report, whoever requested it.

### Known issues
- `run_report` fetches with `ReportScheduler.objects.get(pk=...)`, so a syntactically
  valid but unknown UUID raises `DoesNotExist` and returns a 500 rather than a 404.
  Superuser-only now, so it is a robustness wart rather than an exposure.

## v2026.2.0 — 2026-08-30

Superuser reporting analytics, bulk operations on queued runs, and a substantially richer
Django admin. No model changes, so **no migrations**.

### Added
- **Report Analytics tab** on `/ce/reports/`, superuser-only. Stat tiles (total / ran /
  pending / error), a Runs-by-Report table, a Runs-by-User (Top 25) table, and a
  server-side Scheduled Reports table spanning every user's runs. A window toggle switches
  the summary between 1, 3, 6 and 12 months.
- **`api/run_summary/`** (`?window=1m|3m|6m|12m`) — superuser-only aggregate run counts,
  computed in three `GROUP BY` queries with no per-row fan-out.
- **`api/all_report_scheduler/`** — superuser-only listing of every user's runs. This is a
  separate viewset from `api/report_scheduler/`, whose `created_by=request.user` filter
  remains the authorization boundary for non-superusers and is deliberately untouched.
- **`bulk_actions`** — registry-driven bulk operations over queued runs, via
  `myce.component_registry.ActionRegistry`: `bulk_run_reports` (enqueue) and
  `bulk_delete_reports` (two-phase, with a confirmation modal). Both act on
  `status='pending'` rows **only** — a `ran` row owns an S3 artifact and an audit trail,
  so neither action can touch one. Submitted ids are UUID-validated before reaching the
  queryset, since `filter(id__in=…)` raises on a malformed value.
- **Categories and Available For are editable from the Description tab**, alongside title
  and description, for superusers.
- **Per-user run counts on the `Report` admin change page** — one row per requesting user,
  split by status, all-time.
- **"Run selected pending reports"** admin action on `ReportScheduler`, which enqueues
  asynchronously and reports how many rows it skipped as not pending.
- **A test package** (`report/tests/`) with shared factories, replacing the single-module
  `tests.py`.

### Fixed
- **A `unique_together` collision on report update returned a stock HTML 400 instead of the
  intended JSON error.** The view caught the `IntegrityError` and built the correct JSON
  response, but the un-savepointed failure left the transaction poisoned; `SessionMiddleware`
  then failed its own `request.session.save()`, raising `SessionInterrupted` *after* the view
  had returned, and Django replaced the body. Wrapping only `report.save()` in
  `transaction.atomic()` confines the rollback to a savepoint. The same pattern is worth
  auditing in other JSON views — it converts a JSON response into HTML with no warning.
- **The `Report` admin's category and role filters hid most reports.** `categories` and
  `available_for` are `MultiSelectField`, i.e. a `CharField` holding `"Classes,Students"`,
  so Django's default filter matched `categories__exact='Classes'` — any report in two or
  more categories vanished from every filter. Replaced with `SimpleListFilter`s matching on
  `__contains`.
- **The Scheduled Reports table did not send `format=datatables`**, so the endpoint answered
  with DRF's plain page shape (`{count, next, previous, results}`); DataTables read
  `json.data.length` on it and threw `Cannot read properties of undefined (reading 'length')`,
  leaving the table dead.

### Changed
- **`report_bulk_actions` requires the CE role** (`user_passes_test(user_has_cis_role)`) in
  addition to the per-action superuser check. `ActionRegistry.dispatch` is fail-open by
  design — an action registered without a `permission` kwarg would otherwise be reachable by
  any authenticated user.
- **One queueing implementation, not two.** `queue_pending()` in `report/actions.py` is now
  shared by the admin action and the bulk action, which previously duplicated the
  pending-only filter and its user-facing message.
- **`Report` changelist** shows title, app, categories and roles as human-readable labels,
  with filters and search; **`ReportScheduler` changelist** gains status/report filters,
  requester search, a date hierarchy, `raw_id_fields`, and a truncated `data` column in
  place of the raw JSON blob.
- **`SuperuserOnly` and `_is_superuser` are one predicate**, and the status tuple is derived
  from `ReportScheduler`'s own field choices rather than restated.
- **This changelog**, and `CHANGELOG.md` added to `MANIFEST.in` so it ships in the sdist.

### Known issues
- **The analytics window is measured on `created_on`, which is `auto_now=True`.** Every
  `save()` — including `ReportScheduler.run()` — rewrites it, so the window reflects *last
  modification*, not when the report was requested; a run requested in March but executed
  yesterday counts as this month. The Scheduled Reports column is labelled "Last Updated"
  accordingly. Splitting `created_on` / `updated_on` needs a migration and is deferred to a
  later release. The distortion grows with the window, so it matters most at 6m and 12m.
- **`report/admin.py` and `report/admin/__init__.py` are both tracked.** The package wins on
  import, so behaviour is correct, but the stale module still ships. Left for its own commit.
