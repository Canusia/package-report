# Changelog

All notable changes to `myce_report` (the MyCE reporting framework).

Releases are git-tag-driven on `Canusia/package-report`; each tenant pins a tag through the
`git+https://…@<tag>` line in its `webapp/requirements.txt`. The package's `version` in
`setup.cfg` and `pyproject.toml` always declares the tag it was cut at — pip keys upgrades
off the version string, not the tag, so a frozen version makes an incremental install
silently keep the old code.

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
